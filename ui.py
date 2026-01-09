# Flask UI


from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash
from typing import Any, Dict

from config import load_config, save_config

ui_bp = Blueprint("ui", __name__)

def _as_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default

@ui_bp.route("/settings", methods=["GET", "POST"])
def settings():
    #GET: prikaži formu; POST: snimi config.json.
    cfg = load_config()
    wc = cfg.get("web_client", {})
    us = cfg.get("udp_server", {})

    if request.method == "POST":
        #web_client postavke 
        listen_ip = request.form.get("listen_ip", wc.get("listen_ip", "0.0.0.0")).strip()
        listen_port = _as_int(request.form.get("listen_port", str(wc.get("listen_port", 4001))), 4001)
        metrics_port = _as_int(request.form.get("metrics_listen_port", str(wc.get("metrics_listen_port", 7001))), 7001)
        auto_start = request.form.get("auto_start_receivers") == "on"

        web_host = request.form.get("web_host", wc.get("web_host", "0.0.0.0")).strip()
        web_port = _as_int(request.form.get("web_port", str(wc.get("web_port", 8000))), 8000)

        cfg["web_client"] = {
            **wc,
            "listen_ip": listen_ip,
            "listen_port": listen_port,
            "metrics_listen_port": metrics_port,
            "web_host": web_host,
            "web_port": web_port,
            "auto_start_receivers": auto_start,
        }

        #udp_server postavke 
        client_ip = request.form.get("client_ip", us.get("client_ip", "127.0.0.1")).strip()
        client_port = _as_int(request.form.get("client_port", str(us.get("client_port", 4001))), 4001)
        client_metrics_port = _as_int(request.form.get("client_metrics_port", str(us.get("client_metrics_port", 7001))), 7001)
        camera_index = _as_int(request.form.get("camera_index", str(us.get("camera_index", 0))), 0)
        max_udp_payload = _as_int(request.form.get("max_udp_payload", str(us.get("max_udp_payload", 1300))), 1300)
        jpeg_quality = _as_int(request.form.get("jpeg_quality", str(us.get("jpeg_quality", 70))), 70)
        fps_limit = _as_int(request.form.get("fps_limit", str(us.get("fps_limit", 0))), 0)

        cfg["udp_server"] = {
            **us,
            "client_ip": client_ip,
            "client_port": client_port,
            "client_metrics_port": client_metrics_port,
            "camera_index": camera_index,
            "max_udp_payload": max_udp_payload,
            "jpeg_quality": jpeg_quality,
            "fps_limit": fps_limit,
        }

        save_config(cfg)

        # Ako imamo ReceiverManager u app.config uzimamo nove portove/IP
        manager = ui_bp._app_ctx_stack.top.app.config.get("RECEIVER_MANAGER")  
        if manager is not None:
            manager.apply_config(cfg["web_client"])

        flash("Postavke su sačuvane.", "success")
        return redirect(url_for("ui.settings"))

    us_cmd = _build_udp_server_command(us)
    return render_template("settings.html", wc=wc, us=us, us_cmd=us_cmd, cfg=cfg)

def _build_udp_server_command(us: Dict[str, Any]) -> str:
    #Generisanje komande za pokretanje udp_server-a.
    parts = ["python", "udp_server.py"]
    if us.get("client_ip"):
        parts += ["--client-ip", str(us["client_ip"])]
    if us.get("client_port") is not None:
        parts += ["--client-port", str(us["client_port"])]
    if us.get("client_metrics_port") is not None:
        parts += ["--client-metrics-port", str(us["client_metrics_port"])]
    if us.get("camera_index") is not None:
        parts += ["--camera", str(us["camera_index"])]
    if us.get("fps_limit") is not None:
        parts += ["--fps", str(us["fps_limit"])]
    return " ".join(parts)

@ui_bp.route("/control/<action>", methods=["POST"])
def control(action: str):
    #Start/stop/restart receiver-a u web_client procesu
    cfg = load_config()
    manager = ui_bp._app_ctx_stack.top.app.config.get("RECEIVER_MANAGER") 
    if manager is None:
        flash("Receiver manager nije dostupan.", "error")
        return redirect(url_for("ui.settings"))

    if action == "start":
        manager.start()
        flash("Receiveri su pokrenuti.", "success")
    elif action == "stop":
        manager.stop()
        flash("Receiveri su zaustavljeni.", "success")
    elif action == "restart":
        manager.apply_config(cfg.get("web_client", {}))
        flash("Receiveri su restartovani.", "success")
    else:
        flash("Nepoznata akcija.", "error")

    return redirect(url_for("ui.settings"))
