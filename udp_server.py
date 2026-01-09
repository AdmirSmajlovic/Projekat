import argparse
import cv2
import socket
import time
import json

from protocol import build_packet
from config import load_config, save_config

def parse_args():
    p = argparse.ArgumentParser(description="UDP video server (kamera -> UDP fragmente + server metrike).")
    p.add_argument("--config", default="config.json", help="Putanja do config.json")
    p.add_argument("--client-ip", default=None, help="IP klijenta (override config)")
    p.add_argument("--client-port", type=int, default=None, help="UDP port klijenta za video (override config)")
    p.add_argument("--client-metrics-port", type=int, default=None, help="UDP port klijenta za server metrike (override config)")
    p.add_argument("--camera", type=int, default=None, help="Indeks kamere (override config)")
    p.add_argument("--fps", type=int, default=None, help="FPS limit (0 = bez limita)")
    return p.parse_args()

def main():
    args = parse_args()
    cfg = load_config(args.config)

    us = cfg.get("udp_server", {})

    client_ip = args.client_ip or us.get("client_ip", "127.0.0.1")
    client_port = int(args.client_port if args.client_port is not None else us.get("client_port", 4001))
    client_metrics_port = int(args.client_metrics_port if args.client_metrics_port is not None else us.get("client_metrics_port", 7001))
    camera_index = int(args.camera if args.camera is not None else us.get("camera_index", 0))
    max_udp_payload = int(us.get("max_udp_payload", 1300))
    jpeg_quality = int(us.get("jpeg_quality", 70))
    fps_limit = int(args.fps if args.fps is not None else us.get("fps_limit", 0))

    # Socket za slanje
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Kamera
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Ne mogu otvoriti kameru index={camera_index}")

    # Metrike servera
    frame_id = 0
    bytes_sent = 0
    packets_sent = 0
    last_stats_t = time.time()
    last_bitrate_calc_t = time.time()
    bytes_since_bitrate = 0
    server_fps = 0
    server_bitrate_kbps = 0

    print(f"[UDP SERVER] Šaljem VIDEO na {client_ip}:{client_port}")
    print(f"[UDP SERVER] Šaljem METRIKE na {client_ip}:{client_metrics_port}")
    print(f"[UDP SERVER] max_udp_payload={max_udp_payload}, jpeg_quality={jpeg_quality}, fps_limit={fps_limit}")

    while True:
        t0 = time.time()

        ok, frame = cap.read()
        if not ok:
            continue

        # JPEG encode
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
        ok, buf = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            continue
        jpeg = buf.tobytes()

        # Fragmentacija
        payload_max = max(200, max_udp_payload)  # osiguravamo da payload nije premali
        total_frags = (len(jpeg) + payload_max - 1) // payload_max

        ts_ms = int(time.time() * 1000)

        for frag_id in range(total_frags):
            start = frag_id * payload_max
            end = min(len(jpeg), (frag_id + 1) * payload_max)
            payload = jpeg[start:end]

            pkt = build_packet(
                frame_id=frame_id,
                fragment_id=frag_id,
                total_fragments=total_frags,
                payload=payload,
                timestamp_ms=ts_ms,
            )
            sock.sendto(pkt, (client_ip, client_port))
            packets_sent += 1
            bytes_sent += len(pkt)
            bytes_since_bitrate += len(pkt)

        frame_id += 1

        # server FPS (broj frejmova u sekundi)
        now = time.time()
        if now - last_stats_t >= 1.0:
            server_fps = frame_id / (now - last_stats_t)  # aproksimacija od starta 
            last_stats_t = now

        # bitrate (računanje se vrši svake sekunde)
        if now - last_bitrate_calc_t >= 1.0:
            dt = now - last_bitrate_calc_t
            server_bitrate_kbps = int((bytes_since_bitrate * 8) / dt / 1000)
            bytes_since_bitrate = 0
            last_bitrate_calc_t = now

        # Slanje server metrika
        metrics = {
            "server_fps": int(server_fps),
            "server_bitrate_kbps": int(server_bitrate_kbps),
            "server_bytes_sent": int(bytes_sent),
            "server_packets_sent": int(packets_sent),
            "timestamp_ms": int(time.time() * 1000),
        }
        try:
            sock.sendto(json.dumps(metrics).encode("utf-8"), (client_ip, client_metrics_port))
        except Exception:
            pass

        # FPS limit
        if fps_limit and fps_limit > 0:
            target_dt = 1.0 / fps_limit
            dt = time.time() - t0
            if dt < target_dt:
                time.sleep(target_dt - dt)

if __name__ == "__main__":
    main()
