import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["SECRET_KEY"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.security import hash_secret  # noqa: E402

PW = "Passw0rd!test"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    h = hash_secret(PW)
    for email, role in [("admin@t.io", Role.admin), ("disp@t.io", Role.dispatcher), ("drv@t.io", Role.driver),
                        ("drv2@t.io", Role.driver), ("clinic@t.io", Role.clinic_receiver), ("aud@t.io", Role.auditor)]:
        db.add(User(email=email, name=email.split("@")[0], role=role.value, password_hash=h))
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def login(client, email, password=PW):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def tokens(client):
    return {k: login(client, f"{k}@t.io") for k in ("admin", "disp", "drv", "drv2", "clinic", "aud")}


@pytest.fixture()
def shipment(client, tokens):
    """A freshly created shipment (status=created) assigned to drv & clinic. Returns the creation response."""
    users = {u["email"]: u["id"] for u in client.get("/users", headers=tokens["admin"]).json()}
    r = client.post("/shipments", headers=tokens["disp"], json={
        "origin": "Warehouse", "destination": "Clinic A", "product": "Vaccine",
        "driver_id": users["drv@t.io"], "receiver_id": users["clinic@t.io"], "min_temp": 2, "max_temp": 8})
    assert r.status_code == 201, r.text
    return r.json()
