
# Centralizovano učitavanje i snimanje konfiguracije u config.json

import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "web_client": {
        "listen_ip": "0.0.0.0",
        "listen_port": 4001,
        "metrics_listen_port": 7001,
        "web_host": "0.0.0.0",
        "web_port": 8000,
        "auto_start_receivers": True
    },
    "udp_server": {
        "client_ip": "127.0.0.1",
        "client_port": 4001,
        "client_metrics_port": 7001,
        "camera_index": 0,
        "max_udp_payload": 1300,
        "jpeg_quality": 70,
        "fps_limit": 0
    }
}

def _deep_update(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v
    return dst

def load_config(path: str = "config.json") -> Dict[str, Any]:
    #Učitavanje config.json, ako ne postoji vrati DEFAULT_CONFIG.
    p = Path(path)
    cfg = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    
    merged = json.loads(json.dumps(DEFAULT_CONFIG))

    if isinstance(cfg, dict):
        _deep_update(merged, cfg)

    return merged

def save_config(cfg: Dict[str, Any], path: str = "config.json") -> None:
    # Snimanje konfiguracije u config.json.
    Path(path).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
