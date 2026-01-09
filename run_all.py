# Pokreće udp_server.py i web_client.py na ISTOM računaru
# Omogućava gašenje oba procesa preko button-a "Ugasi program"


from __future__ import annotations

import subprocess
import sys
import time
from typing import Dict

from process_control import write_pids

def main() -> None:
    # Start udp_server (kamera -> UDP)
    udp = subprocess.Popen([sys.executable, "udp_server.py"])
    time.sleep(0.3)

    # Start web_client UI + UDP receiver
    web = subprocess.Popen([sys.executable, "web_client.py"])

    # Zapamti PID-ove (da /shutdown zna šta treba ugasiti)
    pids: Dict[str, int] = {"udp_server": udp.pid, "web_client": web.pid}
    write_pids(pids)

    print("[RUN_ALL] Pokrenuto: udp_server i web_client")
    print("Otvorite UI na: http://127.0.0.1:8000")

    # Čekanje dok se jedan proces ne ugasi
    try:
        while True:
            if udp.poll() is not None or web.poll() is not None:
                break
            time.sleep(0.5)
    finally:
        # Ugasi preostali proces (best-effort)
        for p in (udp, web):
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass

if __name__ == "__main__":
    main()
