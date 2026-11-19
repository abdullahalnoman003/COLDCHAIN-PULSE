from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..access import visibility
from ..database import get_db
from ..models import Alert, Role, Shipment, User
from ..security import require_roles

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(user: User = Depends(require_roles(Role.admin, Role.dispatcher, Role.driver, Role.auditor)),
            db: Session = Depends(get_db)):
    """Aggregates in SQL (no row scans) so the dashboard stays fast at 500+ active shipments."""
    conds = [] if (v := visibility(user)) is None else [v]
    by_status = dict(db.execute(select(Shipment.status, func.count()).where(*conds).group_by(Shipment.status)).all())
    by_alert = dict(db.execute(select(Shipment.alert_state, func.count())
                               .where(Shipment.status == "in_transit", *conds)
                               .group_by(Shipment.alert_state)).all())
    compromised = db.scalar(select(func.count()).select_from(Shipment).where(Shipment.compromised.is_(True), *conds))
    aq = select(Alert.level, func.count()).where(Alert.acknowledged_at.is_(None))
    if conds:
        aq = aq.join(Shipment, Shipment.id == Alert.shipment_id).where(*conds)
    open_alerts = dict(db.execute(aq.group_by(Alert.level)).all())
    return {
        "shipments_by_status": by_status,
        "in_transit_by_alert_state": {k: by_alert.get(k, 0) for k in ("ok", "warning", "critical")},
        "compromised_shipments": compromised,
        "open_alerts": {"warning": open_alerts.get("warning", 0), "critical": open_alerts.get("critical", 0)},
    }
