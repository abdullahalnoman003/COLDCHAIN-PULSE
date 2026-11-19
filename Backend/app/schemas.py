from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth / users ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Role


class UserOut(ORM):
    id: int
    email: EmailStr
    name: str
    role: str
    is_active: bool


# ---------- vehicles ----------
class VehicleCreate(BaseModel):
    plate: str = Field(min_length=2, max_length=32)
    label: str = ""


class VehicleOut(ORM):
    id: int
    plate: str
    label: str
    is_active: bool


# ---------- shipments ----------
class ShipmentCreate(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    origin: str
    destination: str
    product: str = ""
    vehicle_id: int | None = None
    driver_id: int | None = None
    receiver_id: int | None = None
    min_temp: float = 2.0
    max_temp: float = 8.0
    eta: datetime | None = None

    @model_validator(mode="after")
    def _range(self):
        if self.min_temp >= self.max_temp:
            raise ValueError("min_temp must be lower than max_temp")
        return self


class ShipmentUpdate(BaseModel):
    vehicle_id: int | None = None
    driver_id: int | None = None
    receiver_id: int | None = None
    min_temp: float | None = None
    max_temp: float | None = None
    eta: datetime | None = None
    status: Literal["cancelled"] | None = None


class ShipmentOut(ORM):
    id: int
    code: str
    origin: str
    destination: str
    product: str
    vehicle_id: int | None
    driver_id: int | None
    receiver_id: int | None
    min_temp: float
    max_temp: float
    status: str
    eta: datetime | None
    created_at: datetime
    last_temp: float | None
    last_humidity: float | None
    last_reading_at: datetime | None
    alert_state: str
    breach_started_at: datetime | None
    compromised: bool


class ShipmentCreated(ShipmentOut):
    """Returned ONCE at creation: the PINs are never retrievable afterwards."""
    qr_token: str
    pickup_pin: str
    delivery_pin: str


class Page(BaseModel):
    items: list[ShipmentOut]
    total: int
    page: int
    page_size: int


# ---------- telemetry ----------
class ReadingIn(BaseModel):
    temperature: float = Field(ge=-100, le=100)
    humidity: float | None = Field(default=None, ge=0, le=100)
    recorded_at: datetime
    client_uuid: str | None = Field(default=None, max_length=64)


class TelemetryBatchIn(BaseModel):
    shipment_id: int
    readings: list[ReadingIn] = Field(min_length=1, max_length=1000)


class TelemetryOut(ORM):
    id: int
    shipment_id: int
    temperature: float
    humidity: float | None
    recorded_at: datetime
    hash: str


class IngestResult(BaseModel):
    shipment_id: int
    accepted: int
    duplicates: int
    alerts_created: int


# ---------- handoffs ----------
class HandoffIn(BaseModel):
    type: Literal["pickup", "delivery"]
    qr_token: str
    pin: str | None = Field(default=None, max_length=12)
    signature: str | None = Field(default=None, max_length=200_000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    condition: Literal["intact", "damaged", "temperature_concern"] = "intact"
    notes: str | None = Field(default=None, max_length=1000)
    recorded_at: datetime | None = None
    client_uuid: str | None = Field(default=None, max_length=64)


class HandoffOut(ORM):
    id: int
    shipment_id: int
    type: str
    user_id: int
    latitude: float | None
    longitude: float | None
    condition: str
    notes: str | None
    pin_verified: bool
    recorded_at: datetime
    hash: str


class SyncIn(BaseModel):
    """Offline-first driver mode: queued items uploaded in one request."""
    telemetry: list[TelemetryBatchIn] = []
    handoffs: list[tuple[int, HandoffIn]] = []  # [(shipment_id, handoff), ...]


class SyncOut(BaseModel):
    telemetry: list[IngestResult]
    handoffs: list[HandoffOut]
    errors: list[str]


# ---------- alerts / audit ----------
class AlertOut(ORM):
    id: int
    shipment_id: int
    level: str
    message: str
    temperature: float | None
    breach_started_at: datetime | None
    created_at: datetime
    acknowledged_at: datetime | None


class AuditOut(ORM):
    id: int
    event: str
    email: str | None
    user_id: int | None
    ip: str | None
    detail: str | None
    created_at: datetime
