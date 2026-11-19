"""IoT simulator driver: calls POST /simulator/tick every N seconds (default 30, as the brief says).

  python scripts/simulate.py --base-url http://localhost:8000 --email admin@medswift.io \
      --password 'Passw0rd!demo' --interval 30
"""
import argparse
import time

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default="http://localhost:8000")
ap.add_argument("--email", default="admin@medswift.io")
ap.add_argument("--password", default="Passw0rd!demo")
ap.add_argument("--interval", type=float, default=30)
ap.add_argument("--ticks", type=int, default=0, help="0 = run forever")
a = ap.parse_args()

with httpx.Client(base_url=a.base_url, timeout=60) as c:
    tok = c.post("/auth/login", json={"email": a.email, "password": a.password}).raise_for_status().json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    n = 0
    while True:
        r = c.post("/simulator/tick", headers=h)
        if r.status_code == 401:  # token expired
            tok = c.post("/auth/login", json={"email": a.email, "password": a.password}).json()["access_token"]
            h = {"Authorization": f"Bearer {tok}"}
            continue
        print(time.strftime("%H:%M:%S"), r.json())
        n += 1
        if a.ticks and n >= a.ticks:
            break
        time.sleep(a.interval)
