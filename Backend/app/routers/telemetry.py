from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import get_visible_shipment
from ..database import get_db
from ..models import Role, Shipment, User
from ..schemas import IngestResult, SyncIn, SyncOut, TelemetryBatchIn
from ..security import require_roles
from ..services import handoffs as handoff_service
from ..services import telemetry as telemetry_service

router = APIRouter(tags=["telemetry & sync"])


def _shipment_for_ingest(db: Session, user: User, shipment_id: int) -> Shipment:
    s = db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(404, f"Shipment {shipment_id} not found")
    if user.role == Role.driver.value and s.driver_id != user.id:
        raise HTTPException(404, f"Shipment {shipment_id} not found")
    return s


@router.post("/telemetry", response_model=IngestResult, status_code=201)
def ingest_telemetry(data: TelemetryBatchIn, user: User = Depends(require_roles(Role.admin, Role.driver)),
                     db: Session = Depends(get_db)):
    """Single reading or a batch (use a batch to flush an offline queue). Idempotent via client_uuid."""
    s = _shipment_for_ingest(db, user, data.shipment_id)
    res = telemetry_service.ingest(db, s, data.readings)
    db.commit()
    return res


@router.post("/sync", response_model=SyncOut)
def sync(data: SyncIn, user: User = Depends(require_roles(Role.driver, Role.clinic_receiver)),
         db: Session = Depends(get_db)):
    """Offline-first: the PWA uploads everything it queued while offline in ONE call.
    Safe to retry: items carry client_uuid, duplicates are ignored. One bad item never blocks the rest."""
    results, handoffs, errors = [], [], []
    if data.telemetry and user.role != Role.driver.value:
        raise HTTPException(403, "Only drivers can sync telemetry")
    for batch in data.telemetry:
        try:
            s = _shipment_for_ingest(db, user, batch.shipment_id)
            results.append(telemetry_service.ingest(db, s, batch.readings))
            db.commit()
        except HTTPException as e:
            db.rollback()
            errors.append(f"telemetry shipment {batch.shipment_id}: {e.detail}")
    for shipment_id, h in data.handoffs:
        try:
            s = get_visible_shipment(db, user, shipment_id)
            handoffs.append(handoff_service.record_handoff(db, s, user, h))
            db.commit()
        except HTTPException as e:
            db.rollback()
            errors.append(f"handoff shipment {shipment_id} ({h.type}): {e.detail}")
    return SyncOut(telemetry=results, handoffs=handoffs, errors=errors)
