"""Row-level visibility: staff see everything, drivers/receivers only their own shipments."""
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import Role, Shipment, User

STAFF = {Role.admin.value, Role.dispatcher.value, Role.auditor.value}


def visibility(user: User):
    if user.role in STAFF:
        return None
    if user.role == Role.driver.value:
        return Shipment.driver_id == user.id
    if user.role == Role.clinic_receiver.value:
        return Shipment.receiver_id == user.id
    return Shipment.id == -1


def get_visible_shipment(db: Session, user: User, shipment_id: int) -> Shipment:
    s = db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    if user.role == Role.driver.value and s.driver_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    if user.role == Role.clinic_receiver.value and s.receiver_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    return s
