import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..access import get_visible_shipment, visibility
from ..database import get_db
from ..models import Handoff, Role, Shipment, ShipmentStatus, TelemetryLog, User, Vehicle, to_naive_utc
from ..schemas import (HandoffIn, HandoffOut, Page, ShipmentCreate, ShipmentCreated, ShipmentOut,
                       ShipmentUpdate, TelemetryOut)
from ..security import hash_secret, new_pin, require_roles
from ..services import handoffs as handoff_service

router = APIRouter(prefix="/shipments", tags=["shipments"])
ANY = (Role.admin, Role.dispatcher, Role.driver, Role.clinic_receiver, Role.auditor)
MANAGERS = (Role.admin, Role.dispatcher)


def _check_refs(db: Session, vehicle_id, driver_id, receiver_id):
    if vehicle_id is not None and not db.get(Vehicle, vehicle_id):
        raise HTTPException(422, "vehicle_id does not exist")
    for uid, role in ((driver_id, Role.driver), (receiver_id, Role.clinic_receiver)):
        if uid is not None:
            u = db.get(User, uid)
            if not u or u.role != role.value:
                raise HTTPException(422, f"user {uid} is not a {role.value}")


@router.post("", response_model=ShipmentCreated, status_code=201)
def create_shipment(data: ShipmentCreate, user: User = Depends(require_roles(*MANAGERS)),
                    db: Session = Depends(get_db)):
    _check_refs(db, data.vehicle_id, data.driver_id, data.receiver_id)
    code = (data.code or f"CC-{uuid.uuid4().hex[:8].upper()}").upper()
    if db.scalar(select(Shipment.id).where(Shipment.code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Shipment code already exists")
    pickup_pin, delivery_pin = new_pin(), new_pin()
    s = Shipment(
        code=code, origin=data.origin, destination=data.destination, product=data.product,
        vehicle_id=data.vehicle_id, driver_id=data.driver_id, receiver_id=data.receiver_id,
        min_temp=data.min_temp, max_temp=data.max_temp,
        eta=to_naive_utc(data.eta) if data.eta else None, created_by=user.id,
        qr_token=secrets.token_urlsafe(16),
        pickup_pin_hash=hash_secret(pickup_pin), delivery_pin_hash=hash_secret(delivery_pin))
    db.add(s)
    db.commit()
    base = ShipmentOut.model_validate(s).model_dump()
    return ShipmentCreated(**base, qr_token=s.qr_token, pickup_pin=pickup_pin, delivery_pin=delivery_pin)


@router.get("", response_model=Page)
def list_shipments(
    status_: str | None = Query(default=None, alias="status"),
    alert_state: str | None = None,
    compromised: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_roles(*ANY)),
    db: Session = Depends(get_db),
):
    conds = []
    if (v := visibility(user)) is not None:
        conds.append(v)
    if status_:
        conds.append(Shipment.status == status_)
    if alert_state:
        conds.append(Shipment.alert_state == alert_state)
    if compromised is not None:
        conds.append(Shipment.compromised == compromised)
    total = db.scalar(select(func.count()).select_from(Shipment).where(*conds))
    items = db.scalars(select(Shipment).where(*conds).order_by(Shipment.id.desc())
                       .offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{shipment_id}", response_model=ShipmentOut)
def get_shipment(shipment_id: int, user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    return get_visible_shipment(db, user, shipment_id)


@router.patch("/{shipment_id}", response_model=ShipmentOut)
def update_shipment(shipment_id: int, data: ShipmentUpdate, _: User = Depends(require_roles(*MANAGERS)),
                    db: Session = Depends(get_db)):
    s = db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(404, "Shipment not found")
    if s.status == ShipmentStatus.delivered.value:
        raise HTTPException(409, "Delivered shipments are locked")
    changes = data.model_dump(exclude_unset=True)
    _check_refs(db, changes.get("vehicle_id"), changes.get("driver_id"), changes.get("receiver_id"))
    if "eta" in changes and changes["eta"] is not None:
        changes["eta"] = to_naive_utc(changes["eta"])
    for k, v in changes.items():
        setattr(s, k, v)
    if s.min_temp >= s.max_temp:
        raise HTTPException(422, "min_temp must be lower than max_temp")
    db.commit()
    return s


@router.get("/{shipment_id}/qr")
def get_qr(shipment_id: int, _: User = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    """What the dispatcher prints as a QR code on the parcel / delivery note."""
    s = db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(404, "Shipment not found")
    return {"shipment_id": s.id, "code": s.code, "qr_payload": f"coldchain:{s.id}:{s.qr_token}"}


@router.get("/{shipment_id}/telemetry", response_model=list[TelemetryOut])
def shipment_telemetry(shipment_id: int, limit: int = Query(500, ge=1, le=5000),
                       user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    s = get_visible_shipment(db, user, shipment_id)
    rows = db.scalars(select(TelemetryLog).where(TelemetryLog.shipment_id == s.id)
                      .order_by(TelemetryLog.recorded_at.desc(), TelemetryLog.id.desc()).limit(limit)).all()
    return list(reversed(rows))


@router.get("/{shipment_id}/handoffs", response_model=list[HandoffOut])
def shipment_handoffs(shipment_id: int, user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    s = get_visible_shipment(db, user, shipment_id)
    return db.scalars(select(Handoff).where(Handoff.shipment_id == s.id).order_by(Handoff.id)).all()


@router.post("/{shipment_id}/handoffs", response_model=HandoffOut, status_code=201)
def create_handoff(shipment_id: int, data: HandoffIn,
                   user: User = Depends(require_roles(Role.driver, Role.clinic_receiver)),
                   db: Session = Depends(get_db)):
    s = get_visible_shipment(db, user, shipment_id)
    row = handoff_service.record_handoff(db, s, user, data)
    db.commit()
    return row
