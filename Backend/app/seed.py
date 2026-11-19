"""Demo data:  python -m app.seed [--shipments 50] [--in-transit]"""
import argparse

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Role, Shipment, User, Vehicle
from .security import hash_secret
import secrets

DEMO_PASSWORD = "Passw0rd!demo"
DEMO_PIN = "123456"
USERS = [("admin@medswift.io", "Admin", Role.admin), ("dispatcher@medswift.io", "Dispatcher", Role.dispatcher),
         ("auditor@medswift.io", "External Auditor", Role.auditor)]


def seed(n_shipments: int = 20, in_transit: bool = True) -> dict:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    pw = hash_secret(DEMO_PASSWORD)
    demo_pin_hash = hash_secret(DEMO_PIN)  # one hash reused: bcrypt is slow, demo PIN is public anyway

    def user(email, name, role):
        u = db.scalar(select(User).where(User.email == email))
        if not u:
            u = User(email=email, name=name, role=role.value, password_hash=pw)
            db.add(u)
            db.flush()
        return u

    for e, n, r in USERS:
        user(e, n, r)
    drivers = [user(f"driver{i}@medswift.io", f"Driver {i}", Role.driver) for i in range(1, 6)]
    receivers = [user(f"clinic{i}@medswift.io", f"Clinic {i}", Role.clinic_receiver) for i in range(1, 6)]
    vehicles = []
    for i in range(1, 11):
        v = db.scalar(select(Vehicle).where(Vehicle.plate == f"DHK-{1000 + i}"))
        if not v:
            v = Vehicle(plate=f"DHK-{1000 + i}", label=f"Reefer van {i}")
            db.add(v)
            db.flush()
        vehicles.append(v)
    start = db.query(Shipment).count()
    for i in range(n_shipments):
        k = start + i
        db.add(Shipment(
            code=f"DEMO-{k + 1:05d}", origin="Central Warehouse, Dhaka", destination=f"Rural Clinic #{k % 50 + 1}",
            product="mRNA vaccine" if k % 2 else "Insulin", vehicle_id=vehicles[k % 10].id,
            driver_id=drivers[k % 5].id, receiver_id=receivers[k % 5].id, min_temp=2.0, max_temp=8.0,
            status="in_transit" if in_transit else "created", qr_token=secrets.token_urlsafe(16),
            pickup_pin_hash=demo_pin_hash, delivery_pin_hash=demo_pin_hash))
    db.commit()
    db.close()
    return {"password_for_all_demo_users": DEMO_PASSWORD, "demo_pin": DEMO_PIN, "shipments_added": n_shipments}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shipments", type=int, default=20)
    ap.add_argument("--created-only", action="store_true", help="leave shipments in 'created' (need pickup handoff)")
    a = ap.parse_args()
    print(seed(a.shipments, not a.created_only))
