"""Quick load check for the 500+ shipment requirement (the QA team can build on this / use Locust).

  python -m app.seed --shipments 500
  uvicorn app.main:app &          # in another terminal
  python scripts/load_check.py
"""
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE, timeout=60)
tok = c.post("/auth/login", json={"email": "dispatcher@medswift.io", "password": "Passw0rd!demo"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
admin = c.post("/auth/login", json={"email": "admin@medswift.io", "password": "Passw0rd!demo"}).json()["access_token"]

t = time.perf_counter()
print("tick:", c.post("/simulator/tick", headers={"Authorization": f"Bearer {admin}"}).json(), f"{time.perf_counter() - t:.2f}s")


def hit(_):
    t = time.perf_counter()
    r = httpx.get(f"{BASE}/shipments?page_size=200", headers=H, timeout=60)
    return r.status_code, time.perf_counter() - t


with ThreadPoolExecutor(50) as ex:
    res = list(ex.map(hit, range(200)))
lat = sorted(x[1] for x in res)
print("non-200:", sum(1 for s, _ in res if s != 200), "| p50 %.0f ms | p95 %.0f ms" % (
    statistics.median(lat) * 1000, lat[int(len(lat) * 0.95)] * 1000))
