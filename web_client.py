import socket
import time
import threading
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any

import numpy as np
from flask import Flask, Response, jsonify, render_template

from protocol import parse_packet
from config import load_config
from ui import ui_bp

app = Flask(__name__)
app.secret_key = "flash_poruke"  # potrebno za flash poruke 

#Globalni bufferi / metrike
frames_buffer: Dict[int, Dict[int, bytes]] = {}
latest_jpeg: Optional[bytes] = None

metrics_lock = threading.Lock()

client_metrics: Dict[str, Any] = {
    "packets_received": 0,
    "frames_decoded": 0,
    "frames_lost_estimated": 0,
    "bytes_received": 0,
    "last_fps": 0.0,
    "avg_fps": 0.0,
    "last_delay_ms": 0,
    "avg_delay_ms": 0,
    "last_frame_id": -1,
}

server_metrics: Dict[str, Any] = {
    "server_fps": 0,
    "server_bitrate_kbps": 0,
    "server_bytes_sent": 0,
    "server_packets_sent": 0,
    "timestamp_ms": 0
}

#Računanje FPS-a
last_frame_time: Optional[float] = None
fps_samples = []
delay_samples = []
expected_next_frame_id: Optional[int] = None


@dataclass
class WebClientConfig:
    listen_ip: str = "0.0.0.0"
    listen_port: int = 4001
    metrics_listen_port: int = 7001
    auto_start_receivers: bool = True


class ReceiverManager:
    def __init__(self) -> None:
        self.cfg = WebClientConfig()
        self._video_stop = threading.Event()
        self._metrics_stop = threading.Event()
        self._video_thread: Optional[threading.Thread] = None
        self._metrics_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def apply_config(self, cfg_dict: Dict[str, Any]) -> None:
        #Primijenjivanje nove konfiguracije i restartovanje receiver-a
        with self._lock:
            self.cfg.listen_ip = str(cfg_dict.get("listen_ip", self.cfg.listen_ip))
            self.cfg.listen_port = int(cfg_dict.get("listen_port", self.cfg.listen_port))
            self.cfg.metrics_listen_port = int(cfg_dict.get("metrics_listen_port", self.cfg.metrics_listen_port))
            self.cfg.auto_start_receivers = bool(cfg_dict.get("auto_start_receivers", self.cfg.auto_start_receivers))

        self.restart()

    def start(self) -> None:
        with self._lock:
            if self._video_thread and self._video_thread.is_alive():
                return
            self._video_stop.clear()
            self._metrics_stop.clear()

            self._video_thread = threading.Thread(target=udp_video_receiver_loop, args=(self.cfg, self._video_stop), daemon=True)
            self._metrics_thread = threading.Thread(target=udp_metrics_receiver_loop, args=(self.cfg, self._metrics_stop), daemon=True)
            self._video_thread.start()
            self._metrics_thread.start()

    def stop(self) -> None:
        self._video_stop.set()
        self._metrics_stop.set()

    def restart(self) -> None:
        self.stop()
        time.sleep(0.2)
        self.start()

    def is_running(self) -> bool:
        return bool(self._video_thread and self._video_thread.is_alive())


def udp_video_receiver_loop(cfg: WebClientConfig, stop_event: threading.Event):
    #Primanje video paketa, sklapanje frame-ova i računanje KLIJENTSKIH metrika
    global latest_jpeg, last_frame_time, expected_next_frame_id

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    try:
        sock.bind((cfg.listen_ip, cfg.listen_port))
    except OSError as e:
        print(f"[WEB CLIENT] Ne mogu bindati video socket na {cfg.listen_ip}:{cfg.listen_port} -> {e}")
        return

    sock.settimeout(1.0)
    print(f"[WEB CLIENT] Slušam VIDEO UDP na {cfg.listen_ip}:{cfg.listen_port}")

    try:
        while not stop_event.is_set():
            try:
                packet, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            with metrics_lock:
                client_metrics["packets_received"] += 1
                client_metrics["bytes_received"] += len(packet)

            try:
                header, payload = parse_packet(packet)
            except ValueError as e:
                print("[WEB CLIENT] Greška paketa:", e)
                continue

            fid = header["frame_id"]
            frag_id = header["fragment_id"]
            total = header["total_fragments"]

            now_ms = int(time.time() * 1000)
            # purge nepotpunih frame-ova da se buffer ne gomila (npr. > 300ms)
            stale_before = now_ms - 300
            for old_fid in list(frames_buffer.keys()):
            # Heuristika: ako je fid "previše iza" očekivanog, odbaci
                if expected_next_frame_id is not None and old_fid < expected_next_frame_id - 5:
                    del frames_buffer[old_fid]


            # Procjena izgubljenih frame-ova
            if expected_next_frame_id is None:
                expected_next_frame_id = fid
            else:
                if fid > expected_next_frame_id:
                    lost = fid - expected_next_frame_id
                    with metrics_lock:
                        client_metrics["frames_lost_estimated"] += lost
                    expected_next_frame_id = fid

            # Buffer fragmenta
            if fid not in frames_buffer:
                frames_buffer[fid] = {}
            frames_buffer[fid][frag_id] = payload

            # Ako smo dobili sve fragmente
            if len(frames_buffer[fid]) == total:
                full = b"".join(frames_buffer[fid][i] for i in range(total))
                del frames_buffer[fid]

                latest_jpeg = full

                with metrics_lock:
                    client_metrics["frames_decoded"] += 1
                    client_metrics["last_frame_id"] = fid

                # FPS + delay na strani klijenta
                if last_frame_time is not None:
                    dt = time.time() - last_frame_time
                    if dt > 0:
                        fps = 1.0 / dt
                        fps_samples.append(fps)
                        fps_samples[:] = fps_samples[-60:]

                        with metrics_lock:
                            client_metrics["last_fps"] = fps
                            client_metrics["avg_fps"] = sum(fps_samples) / len(fps_samples)

                last_frame_time = time.time()

                # delay: trenutni time - header timestamp (ako postoji)
                ts = header.get("timestamp_ms", 0) or 0
                if ts:
                    d = max(0, now_ms - int(ts))
                    delay_samples.append(d)
                    delay_samples[:] = delay_samples[-60:]
                    with metrics_lock:
                        client_metrics["last_delay_ms"] = int(d)
                        client_metrics["avg_delay_ms"] = int(sum(delay_samples) / len(delay_samples))

    finally:
        try:
            sock.close()
        except Exception:
            pass
        print("[WEB CLIENT] VIDEO receiver zaustavljen.")


def udp_metrics_receiver_loop(cfg: WebClientConfig, stop_event: threading.Event):
    """Prima SERVER metrike preko UDP-a."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((cfg.listen_ip, cfg.metrics_listen_port))
    except OSError as e:
        print(f"[WEB CLIENT] Ne mogu bindati metrics socket na {cfg.listen_ip}:{cfg.metrics_listen_port} -> {e}")
        return

    sock.settimeout(1.0)
    print(f"[WEB CLIENT] Slušam SERVER METRIKE UDP na {cfg.listen_ip}:{cfg.metrics_listen_port}")

    try:
        while not stop_event.is_set():
            try:
                data, _addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                m = json.loads(data.decode("utf-8", errors="ignore"))
            except Exception:
                continue

            with metrics_lock:
                server_metrics.update(m)

    finally:
        try:
            sock.close()
        except Exception:
            pass
        print("[WEB CLIENT] METRIKE receiver zaustavljen.")


def gen_mjpeg():
    """Streaming endpoint za <img src="/video">."""
    global latest_jpeg
    while True:
        if latest_jpeg is None:
            time.sleep(0.005)
            continue
        frame = latest_jpeg
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.005)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video")
def video_feed():
    return Response(gen_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/metrics")
def metrics():
    with metrics_lock:
        m_client = dict(client_metrics)
        m_server = dict(server_metrics)
    return jsonify({"client": m_client, "server": m_server})


@app.route("/health")
def health():
    cfg = load_config().get("web_client", {})
    return jsonify({
        "ok": True,
        "receivers_running": receiver_manager.is_running(),
        "web_client_config": cfg
    })

@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Ugasi web_client; ako je pokrenuto preko run_all.py, ugasi i udp_server."""
    # Pokušaj ugasiti udp_server ako postoji pids.json run_all.py ga kreira
    try:
        from process_control import terminate_known_processes
        terminate_known_processes(skip="web_client")
    except Exception:
        pass

    # Pokušaj za shutdown
    func = None
    try:
        from flask import request
        func = request.environ.get("werkzeug.server.shutdown")
    except Exception:
        func = None

    if func is not None:
        func()
        return jsonify({"ok": True, "message": "Shutdown requested"})
    else:
        import os
        os._exit(0)


# UI settings + controls
app.register_blueprint(ui_bp)

receiver_manager = ReceiverManager()
app.config["RECEIVER_MANAGER"] = receiver_manager

if __name__ == "__main__":
    cfg = load_config()
    wc = cfg.get("web_client", {})

    # Konfiguriši pri pokretanju
    receiver_manager.apply_config(wc)

    # Pokreni jedino ako je omogućeno
    if bool(wc.get("auto_start_receivers", True)):
        receiver_manager.start()

    # Flask web server host/port se čitaju iz config.json-a
    host = str(wc.get("web_host", "0.0.0.0"))
    port = int(wc.get("web_port", 8000))
    print(f"[WEB CLIENT] Web UI: http://{host}:{port} (ako je host 0.0.0.0, otvori sa IP adrese računara)")
    app.run(host=host, port=port, debug=False, threaded=True)
