# Pomoćni modul za run_all.py
# - pids.json sadrži PID-ove udp_server i web_client
# - terminate_known_processes() šalje SIGTERM na procese


from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from typing import Dict, Any, Optional

PID_FILE = Path("pids.json")

def write_pids(pids: Dict[str, int]) -> None:
    #Snimanje PID-ova u pids.json
    PID_FILE.write_text(json.dumps(pids, indent=2), encoding="utf-8")

def read_pids() -> Dict[str, int]:
    #Učitavanje PID-ova iz pids.json."""
    if PID_FILE.exists():
        try:
            return json.loads(PID_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _terminate_pid(pid: int) -> bool:
    #Slanje SIGTERM procesu.
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False

def terminate_known_processes(skip: Optional[str] = None) -> Dict[str, Any]:
    #Gašenje procesa iz pids.json 
    pids = read_pids()
    result: Dict[str, Any] = {"pids": pids, "terminated": {}, "errors": {}}

    for name, pid in list(pids.items()):
        if skip and name == skip:
            continue
        ok = _terminate_pid(int(pid))
        if ok:
            result["terminated"][name] = pid
        else:
            result["errors"][name] = pid
    return result
