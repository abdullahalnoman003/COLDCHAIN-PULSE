"""Database schema.

Append-only tables (TelemetryLog, Handoff, AuditLog) are protected two ways:
  1. the API exposes no update/delete route for them
  2. SQLAlchemy ORM events raise if anyone tries to UPDATE/DELETE a row
Each telemetry/handoff row also carries a SHA-256 hash chained to the previous
row of the same shipment, so silent edits made directly in the DB are detectable.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint, event)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """Naive UTC datetime (consistent across SQLite and Postgres)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class Role(str, enum.Enum):
    admin = "admin"
    dispatcher = "dispatcher"
    driver = "driver"
    clinic_receiver = "clinic_receiver"
    auditor = "auditor"


class ShipmentStatus(str, enum.Enum):
    created = "created"
    in_transit = "in_transit"
    delivered = "delivered"
    cancelled = "cancelled"


class AlertLevel(str, enum.Enum):
    warning = "warning"
    critical = "critical"


class HandoffType(str, enum.Enum):
    pickup = "pickup"
    delivery = "delivery"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(32), unique=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    origin: Mapped[str] = mapped_column(String(255))
    destination: Mapped[str] = mapped_column(String(255))
    product: Mapped[str] = mapped_column(String(255), default="")
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    receiver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    min_temp: Mapped[float] = mapped_column(Float, default=2.0)
    max_temp: Mapped[float] = mapped_column(Float, default=8.0)
    status: Mapped[str] = mapped_column(String(20), default=ShipmentStatus.created.value, index=True)
    eta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Handoff credentials (QR token plain, PINs hashed)
    qr_token: Mapped[str] = mapped_column(String(64), unique=True)
    pickup_pin_hash: Mapped[str] = mapped_column(String(255))
    delivery_pin_hash: Mapped[str] = mapped_column(String(255))

    # Denormalised "live" fields so the dashboard never scans the telemetry table
    last_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_reading_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    alert_state: Mapped[str] = mapped_column(String(16), default="ok")  # ok|warning|critical
    breach_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    compromised: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    telemetry_head: Mapped[str | None] = mapped_column(String(64), nullable=True)
    handoff_head: Mapped[str | None] = mapped_column(String(64), nullable=True)

    vehicle: Mapped["Vehicle | None"] = relationship()
    driver: Mapped["User | None"] = relationship(foreign_keys=[driver_id])
    receiver: Mapped["User | None"] = relationship(foreign_keys=[receiver_id])


class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"
    __table_args__ = (
        UniqueConstraint("shipment_id", "client_uuid", name="uq_telemetry_client"),
        Index("ix_telemetry_shipment_time", "shipment_id", "recorded_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"))
    client_uuid: Mapped[str] = mapped_column(String(64))
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash: Mapped[str] = mapped_column(String(64))


class Handoff(Base):
    __tablename__ = "handoffs"
    __table_args__ = (UniqueConstraint("shipment_id", "client_uuid", name="uq_handoff_client"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    client_uuid: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    condition: Mapped[str] = mapped_column(String(32))  # intact | damaged | temperature_concern
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash: Mapped[str] = mapped_column(String(64))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(String(500))
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    breach_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event: Mapped[str] = mapped_column(String(64), index=True)  # login_failed, login_ok, ...
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AppendOnlyError(RuntimeError):
    pass


def _block(mapper, connection, target):
    raise AppendOnlyError(f"{type(target).__name__} is append-only: updates/deletes are not allowed")


for _model in (TelemetryLog, Handoff, AuditLog):
    event.listen(_model, "before_update", _block)
    event.listen(_model, "before_delete", _block)
