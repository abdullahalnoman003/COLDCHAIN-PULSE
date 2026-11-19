"""SHA-256 hash chain helpers (tamper evidence for append-only logs)."""
import hashlib
import hmac
import json

from ..config import settings

GENESIS = "GENESIS"


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def chain_hash(prev: str | None, payload: dict) -> str:
    return hashlib.sha256(((prev or GENESIS) + canonical(payload)).encode()).hexdigest()


def telemetry_payload(row) -> dict:
    return {
        "shipment_id": row.shipment_id,
        "client_uuid": row.client_uuid,
        "temperature": row.temperature,
        "humidity": row.humidity,
        "recorded_at": row.recorded_at.isoformat(),
    }


def handoff_payload(row) -> dict:
    return {
        "shipment_id": row.shipment_id,
        "client_uuid": row.client_uuid,
        "type": row.type,
        "user_id": row.user_id,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "condition": row.condition,
        "notes": row.notes,
        "signature": row.signature,
        "pin_verified": row.pin_verified,
        "recorded_at": row.recorded_at.isoformat(),
    }


def verify_chain(rows, payload_fn) -> dict:
    """rows must be ordered by id. Returns {valid, count, head, broken_at_id}."""
    prev = None
    for row in rows:
        if row.prev_hash != prev or chain_hash(prev, payload_fn(row)) != row.hash:
            return {"valid": False, "count": len(rows), "head": prev, "broken_at_id": row.id}
        prev = row.hash
    return {"valid": True, "count": len(rows), "head": prev, "broken_at_id": None}


def sign_report(data: dict) -> str:
    return hmac.new(settings.secret_key.encode(), canonical(data).encode(), hashlib.sha256).hexdigest()
