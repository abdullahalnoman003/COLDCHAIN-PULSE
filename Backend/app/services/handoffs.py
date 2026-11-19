import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Handoff, Role, Shipment, ShipmentStatus, User, to_naive_utc, utcnow
from ..schemas import HandoffIn
from ..security import verify_secret
from . import integrity


def record_handoff(db: Session, s: Shipment, user: User, data: HandoffIn) -> Handoff:
    # Idempotent replay of an offline-queued handoff
    if data.client_uuid:
        existing = db.scalar(select(Handoff).where(
            Handoff.shipment_id == s.id, Handoff.client_uuid == data.client_uuid))
        if existing:
            return existing

    # Who may sign what
    if data.type == "pickup":
        if user.role != Role.driver.value or s.driver_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the assigned driver can sign pickup")
    else:
        if user.role != Role.clinic_receiver.value or s.receiver_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the assigned clinic receiver can sign delivery")

    # Credentials: QR must match; PIN (if given) must match; at least PIN or signature required
    if data.qr_token != s.qr_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "QR code does not match this shipment")
    if not data.pin and not data.signature:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PIN or signature required")
    pin_ok = False
    if data.pin:
        pin_hash = s.pickup_pin_hash if data.type == "pickup" else s.delivery_pin_hash
        pin_ok = verify_secret(data.pin, pin_hash)
        if not pin_ok:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Wrong PIN")

    # State machine
    prior = {h.type for h in db.scalars(select(Handoff).where(Handoff.shipment_id == s.id))}
    if data.type in prior:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{data.type} already recorded")
    if data.type == "pickup" and s.status != ShipmentStatus.created.value:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot pick up a shipment that is {s.status}")
    if data.type == "delivery" and "pickup" not in prior:
        raise HTTPException(status.HTTP_409_CONFLICT, "Delivery requires a recorded pickup first")

    row = Handoff(
        shipment_id=s.id, client_uuid=data.client_uuid or uuid.uuid4().hex, type=data.type, user_id=user.id,
        latitude=data.latitude, longitude=data.longitude, condition=data.condition, notes=data.notes,
        signature=data.signature, pin_verified=pin_ok,
        recorded_at=to_naive_utc(data.recorded_at) if data.recorded_at else utcnow(),
        prev_hash=s.handoff_head)
    row.hash = integrity.chain_hash(row.prev_hash, integrity.handoff_payload(row))
    db.add(row)
    s.handoff_head = row.hash
    s.status = ShipmentStatus.in_transit.value if data.type == "pickup" else ShipmentStatus.delivered.value
    if data.condition != "intact" and data.type == "delivery":
        s.compromised = True
    return row
