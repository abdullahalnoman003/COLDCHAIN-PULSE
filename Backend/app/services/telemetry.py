import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Shipment, TelemetryLog, to_naive_utc
from ..schemas import IngestResult, ReadingIn
from . import alerts, integrity


def ingest(db: Session, s: Shipment, readings: list[ReadingIn]) -> IngestResult:
    """Append readings (idempotent via client_uuid) and run the alert engine in time order."""
    ordered = sorted(readings, key=lambda r: to_naive_utc(r.recorded_at))
    uuids = [r.client_uuid for r in ordered if r.client_uuid]
    seen: set[str] = set()
    if uuids:
        seen = set(db.scalars(select(TelemetryLog.client_uuid).where(
            TelemetryLog.shipment_id == s.id, TelemetryLog.client_uuid.in_(uuids))))
    accepted = dup = n_alerts = 0
    for r in ordered:
        if r.client_uuid and r.client_uuid in seen:
            dup += 1
            continue
        row = TelemetryLog(
            shipment_id=s.id, client_uuid=r.client_uuid or uuid.uuid4().hex,
            temperature=r.temperature, humidity=r.humidity,
            recorded_at=to_naive_utc(r.recorded_at), prev_hash=s.telemetry_head)
        row.hash = integrity.chain_hash(row.prev_hash, integrity.telemetry_payload(row))
        db.add(row)
        s.telemetry_head = row.hash
        n_alerts += len(alerts.apply_reading(db, s, row))
        if r.client_uuid:
            seen.add(r.client_uuid)
        accepted += 1
    return IngestResult(shipment_id=s.id, accepted=accepted, duplicates=dup, alerts_created=n_alerts)
