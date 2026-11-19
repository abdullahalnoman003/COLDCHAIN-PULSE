from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import AppendOnlyError, AuditLog, Handoff, Shipment, TelemetryLog
from conftest import PW, login

T0 = datetime(2026, 11, 19, 10, 0, 0, tzinfo=timezone.utc)


def pickup(client, tokens, s, **kw):
    body = {"type": "pickup", "qr_token": s["qr_token"], "pin": s["pickup_pin"], "latitude": 23.8, "longitude": 90.4}
    body.update(kw)
    return client.post(f"/shipments/{s['id']}/handoffs", headers=tokens["drv"], json=body)


def readings(temps, start=T0, step_s=30, prefix="r"):
    return [{"temperature": t, "humidity": 50, "recorded_at": (start + timedelta(seconds=step_s * i)).isoformat(),
             "client_uuid": f"{prefix}{i}"} for i, t in enumerate(temps)]


def send(client, tokens, s, temps, who="admin", **kw):
    r = client.post("/telemetry", headers=tokens[who], json={"shipment_id": s["id"], "readings": readings(temps, **kw)})
    assert r.status_code == 201, r.text
    return r.json()


# ---------- auth / security ----------
def test_requires_auth_and_hashed_passwords(client):
    assert client.get("/shipments").status_code == 401
    db = SessionLocal()
    from app.models import User
    assert all(u.password_hash.startswith("$2") for u in db.scalars(select(User)))


def test_failed_logins_are_audited_and_lock_out(client, tokens):
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "drv@t.io", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"email": "drv@t.io", "password": PW}).status_code == 429
    logs = client.get("/audit-logs?event=login_failed", headers=tokens["aud"]).json()
    assert len(logs) == 5


@pytest.mark.parametrize("method,path,role,expected", [
    ("post", "/shipments", "drv", 403), ("post", "/shipments", "aud", 403), ("post", "/users", "disp", 403),
    ("get", "/users", "drv", 403), ("get", "/audit-logs", "disp", 403), ("post", "/simulator/tick", "disp", 403),
    ("get", "/reports/shipments/1/verify", "drv", 403), ("get", "/reports/shipments/1/verify", "clinic", 403),
])
def test_rbac_matrix(client, tokens, method, path, role, expected):
    assert client.request(method.upper(), path, headers=tokens[role]).status_code == expected


def test_auditor_is_read_only(client, tokens, shipment):
    assert client.get("/shipments", headers=tokens["aud"]).status_code == 200
    assert client.patch(f"/shipments/{shipment['id']}", headers=tokens["aud"], json={"max_temp": 9}).status_code == 403
    assert client.post("/telemetry", headers=tokens["aud"],
                       json={"shipment_id": shipment["id"], "readings": readings([5])}).status_code == 403


def test_driver_sees_only_own_shipments(client, tokens, shipment):
    assert client.get("/shipments", headers=tokens["drv"]).json()["total"] == 1
    assert client.get("/shipments", headers=tokens["drv2"]).json()["total"] == 0
    assert client.get(f"/shipments/{shipment['id']}", headers=tokens["drv2"]).status_code == 404


def test_pins_not_leaked_afterwards(client, tokens, shipment):
    body = client.get(f"/shipments/{shipment['id']}", headers=tokens["disp"]).json()
    assert "pickup_pin" not in body and "qr_token" not in body and "pickup_pin_hash" not in body


# ---------- handoff ----------
def test_handoff_flow_and_rules(client, tokens, shipment):
    s = shipment
    assert pickup(client, tokens, s, pin="000000").status_code == 400          # wrong PIN
    assert pickup(client, tokens, s, qr_token="nope").status_code == 400       # wrong QR
    assert pickup(client, tokens, s, pin=None).status_code == 400              # need PIN or signature
    r = pickup(client, tokens, s, client_uuid="h1")
    assert r.status_code == 201 and r.json()["pin_verified"] is True
    assert pickup(client, tokens, s, client_uuid="h1").json()["id"] == r.json()["id"]  # idempotent replay
    assert pickup(client, tokens, s, client_uuid="h2").status_code == 409      # already picked up
    assert client.get(f"/shipments/{s['id']}", headers=tokens["drv"]).json()["status"] == "in_transit"
    deliver = {"type": "delivery", "qr_token": s["qr_token"], "signature": "data:image/png;base64,AAA", "condition": "intact"}
    assert client.post(f"/shipments/{s['id']}/handoffs", headers=tokens["drv"], json=deliver).status_code == 403
    assert client.post(f"/shipments/{s['id']}/handoffs", headers=tokens["clinic"], json=deliver).status_code == 201
    assert client.get(f"/shipments/{s['id']}", headers=tokens["disp"]).json()["status"] == "delivered"


def test_delivery_requires_pickup(client, tokens, shipment):
    r = client.post(f"/shipments/{shipment['id']}/handoffs", headers=tokens["clinic"],
                    json={"type": "delivery", "qr_token": shipment["qr_token"], "pin": shipment["delivery_pin"]})
    assert r.status_code == 409


# ---------- telemetry & alert engine ----------
def test_no_alerts_for_normal_temps(client, tokens, shipment):
    pickup(client, tokens, shipment)
    assert send(client, tokens, shipment, [5.0] * 10)["alerts_created"] == 0


def test_warning_when_approaching_limit_once(client, tokens, shipment):
    pickup(client, tokens, shipment)
    assert send(client, tokens, shipment, [5, 7.5, 7.6, 7.7])["alerts_created"] == 1
    alerts = client.get("/alerts", headers=tokens["disp"]).json()
    assert [a["level"] for a in alerts] == ["warning"]


def test_critical_only_after_10_minutes_breach(client, tokens, shipment):
    pickup(client, tokens, shipment)
    # 9.5 min out of range (20 readings, 30 s apart) -> only a warning
    send(client, tokens, shipment, [5] + [9.5] * 20, prefix="a")
    assert [a["level"] for a in client.get("/alerts", headers=tokens["disp"]).json()] == ["warning"]
    # keep breaching past 10 min -> exactly one critical
    send(client, tokens, shipment, [9.5] * 10, start=T0 + timedelta(minutes=11), prefix="b")
    send(client, tokens, shipment, [9.8] * 10, start=T0 + timedelta(minutes=17), prefix="c")
    levels = sorted(a["level"] for a in client.get("/alerts", headers=tokens["disp"]).json())
    assert levels == ["critical", "warning"]
    s = client.get(f"/shipments/{shipment['id']}", headers=tokens["disp"]).json()
    assert s["compromised"] is True and s["alert_state"] == "critical"


def test_short_spike_never_goes_critical(client, tokens, shipment):
    pickup(client, tokens, shipment)
    send(client, tokens, shipment, [5, 9, 9, 9, 5, 5, 5], prefix="a")
    send(client, tokens, shipment, [5, 9, 9, 9, 5], start=T0 + timedelta(minutes=30), prefix="b")
    assert all(a["level"] == "warning" for a in client.get("/alerts", headers=tokens["disp"]).json())


def test_telemetry_idempotent_offline_sync(client, tokens, shipment):
    pickup(client, tokens, shipment)
    first = send(client, tokens, shipment, [5, 5, 5], who="drv")
    again = send(client, tokens, shipment, [5, 5, 5], who="drv")
    assert first["accepted"] == 3 and again["accepted"] == 0 and again["duplicates"] == 3


def test_sync_endpoint_handles_mixed_queue_and_bad_items(client, tokens, shipment):
    s = shipment
    body = {
        "telemetry": [{"shipment_id": s["id"], "readings": readings([5, 5])},
                      {"shipment_id": 9999, "readings": readings([5])}],
        "handoffs": [[s["id"], {"type": "pickup", "qr_token": s["qr_token"], "pin": s["pickup_pin"], "client_uuid": "q1"}]],
    }
    r = client.post("/sync", headers=tokens["drv"], json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["telemetry"][0]["accepted"] == 2 and len(out["handoffs"]) == 1 and len(out["errors"]) == 1
    assert client.post("/sync", headers=tokens["drv"], json=body).json()["telemetry"][0]["duplicates"] == 2


def test_driver_cannot_post_other_drivers_telemetry(client, tokens, shipment):
    r = client.post("/telemetry", headers=tokens["drv2"], json={"shipment_id": shipment["id"], "readings": readings([5])})
    assert r.status_code == 404


# ---------- data integrity ----------
def test_no_update_or_delete_routes_for_logs(client, tokens, shipment):
    for path in ("/telemetry", f"/shipments/{shipment['id']}/telemetry", f"/shipments/{shipment['id']}/handoffs",
                 "/audit-logs"):
        for m in ("put", "patch", "delete"):
            assert getattr(client, m)(path, headers=tokens["admin"]).status_code in (404, 405)


def test_orm_blocks_edit_and_delete(client, tokens, shipment):
    pickup(client, tokens, shipment)
    send(client, tokens, shipment, [5])
    db = SessionLocal()
    for model in (TelemetryLog, Handoff, AuditLog):
        row = db.scalars(select(model)).first()
        row_id = row.id
        row_col = "temperature" if model is TelemetryLog else ("condition" if model is Handoff else "detail")
        setattr(row, row_col, "tampered" if model is not TelemetryLog else 99.0)
        with pytest.raises(AppendOnlyError):
            db.commit()
        db.rollback()
        with pytest.raises(AppendOnlyError):
            db.delete(db.get(model, row_id))
            db.commit()
        db.rollback()


def test_hash_chain_detects_tampering(client, tokens, shipment):
    pickup(client, tokens, shipment)
    send(client, tokens, shipment, [5, 5.1, 5.2, 5.3])
    v = client.get(f"/reports/shipments/{shipment['id']}/verify", headers=tokens["aud"]).json()
    assert v["tamper_free"] is True
    # attacker edits the DB directly (bypassing the ORM)
    from app.database import engine
    from sqlalchemy import text
    with engine.begin() as c:
        c.execute(text("UPDATE telemetry_logs SET temperature = 4.0 WHERE id = 2"))
    v = client.get(f"/reports/shipments/{shipment['id']}/verify", headers=tokens["aud"]).json()
    assert v["tamper_free"] is False and v["telemetry"]["broken_at_id"] == 2


# ---------- reports / dashboard / simulator ----------
def test_reports_csv_pdf(client, tokens, shipment):
    pickup(client, tokens, shipment)
    send(client, tokens, shipment, [5] + [9.5] * 30)
    csv_r = client.get(f"/reports/shipments/{shipment['id']}.csv", headers=tokens["aud"])
    assert csv_r.status_code == 200 and "report_signature_hmac_sha256" in csv_r.text and "telemetry" in csv_r.text
    pdf = client.get(f"/reports/shipments/{shipment['id']}.pdf", headers=tokens["aud"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_dashboard_and_simulator(client, tokens, shipment):
    pickup(client, tokens, shipment)
    r = client.post("/simulator/tick", headers=tokens["admin"])
    assert r.json()["readings"] == 1
    d = client.get("/dashboard/summary", headers=tokens["disp"]).json()
    assert d["shipments_by_status"]["in_transit"] == 1
    assert client.get("/dashboard/summary", headers=tokens["drv2"]).json()["shipments_by_status"] == {}


def test_validation(client, tokens):
    r = client.post("/shipments", headers=tokens["disp"], json={"origin": "a", "destination": "b", "min_temp": 9, "max_temp": 8})
    assert r.status_code == 422
    r = client.post("/shipments", headers=tokens["disp"], json={"origin": "a", "destination": "b", "driver_id": 5})  # 5 = clinic user
    assert r.status_code == 422
