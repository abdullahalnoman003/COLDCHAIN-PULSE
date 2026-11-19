from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Role, User
from ..schemas import AuditOut
from ..security import require_roles
from ..services import simulator

router = APIRouter(tags=["admin"])


@router.get("/audit-logs", response_model=list[AuditOut])
def audit_logs(event: str | None = None, limit: int = Query(100, ge=1, le=1000),
               _: User = Depends(require_roles(Role.admin, Role.auditor)), db: Session = Depends(get_db)):
    q = select(AuditLog)
    if event:
        q = q.where(AuditLog.event == event)
    return db.scalars(q.order_by(AuditLog.id.desc()).limit(limit)).all()


@router.post("/simulator/tick")
def simulator_tick(_: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    """Generate one temp/humidity reading for every in-transit shipment. Call every 30 s
    (scripts/simulate.py does this) — serverless hosts can't run background loops."""
    return simulator.tick(db)
