from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import visibility
from ..database import get_db
from ..models import Alert, Role, Shipment, User, utcnow
from ..schemas import AlertOut
from ..security import require_roles

router = APIRouter(prefix="/alerts", tags=["alerts"])
ALERT_ROLES = (Role.admin, Role.dispatcher, Role.driver, Role.auditor)


@router.get("", response_model=list[AlertOut])
def list_alerts(level: str | None = None, unacknowledged: bool = False, since: datetime | None = None,
                shipment_id: int | None = None, limit: int = Query(100, ge=1, le=500),
                user: User = Depends(require_roles(*ALERT_ROLES)), db: Session = Depends(get_db)):
    """Dispatchers see all alerts, drivers only their own shipments'. Poll with ?since=<last created_at>."""
    q = select(Alert)
    if (v := visibility(user)) is not None:
        q = q.join(Shipment, Shipment.id == Alert.shipment_id).where(v)
    if level:
        q = q.where(Alert.level == level)
    if unacknowledged:
        q = q.where(Alert.acknowledged_at.is_(None))
    if since:
        q = q.where(Alert.created_at > since.replace(tzinfo=None))
    if shipment_id:
        q = q.where(Alert.shipment_id == shipment_id)
    return db.scalars(q.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)).all()


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: int, user: User = Depends(require_roles(Role.admin, Role.dispatcher, Role.driver)),
                db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    if user.role == Role.driver.value:
        s = db.get(Shipment, a.shipment_id)
        if s.driver_id != user.id:
            raise HTTPException(404, "Alert not found")
    if a.acknowledged_at is None:
        a.acknowledged_at, a.acknowledged_by = utcnow(), user.id
        db.commit()
    return a
