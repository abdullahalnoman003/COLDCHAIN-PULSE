"""IoT simulator: one reading (temp + humidity) per in-transit shipment per tick (call every 30 s).

Stateless & deterministic-ish so it works on serverless (Vercel has no background loops):
  * normal shipments hover around the middle of their range
  * every 10th shipment (id % 10 == 3) has a 'faulty reefer' that breaches for 20 min of every hour
    -> produces 1 warning, then 1 critical after 10 min, then recovers
"""
import math
import random
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Shipment, ShipmentStatus, utcnow
from ..schemas import ReadingIn
from . import telemetry


def make_reading(s: Shipment, now: datetime, rng: random.Random, faulty: bool | None = None) -> ReadingIn:
    mid = (s.min_temp + s.max_temp) / 2
    half = (s.max_temp - s.min_temp) / 2
    t = mid + 0.35 * half * math.sin(now.timestamp() / 900 + s.id) + rng.gauss(0, 0.08 * half)
    if faulty is None:
        faulty = s.id % 10 == 3
    if faulty and (now.minute // 20) % 3 == 2:
        t = s.max_temp + 1.2 + rng.random()  # sustained breach
    hum = max(0.0, min(100.0, 45 + 8 * math.sin(now.timestamp() / 1200 + s.id) + rng.gauss(0, 1.5)))
    return ReadingIn(temperature=round(t, 2), humidity=round(hum, 1), recorded_at=now, client_uuid=uuid.uuid4().hex)


def tick(db: Session, now: datetime | None = None, seed: int | None = None) -> dict:
    now = now or utcnow()
    rng = random.Random(seed)
    shipments = db.scalars(select(Shipment).where(Shipment.status == ShipmentStatus.in_transit.value)).all()
    accepted = alerts = 0
    for s in shipments:
        res = telemetry.ingest(db, s, [make_reading(s, now, rng)])
        accepted += res.accepted
        alerts += res.alerts_created
    db.commit()
    return {"shipments": len(shipments), "readings": accepted, "alerts_created": alerts, "at": now.isoformat()}
