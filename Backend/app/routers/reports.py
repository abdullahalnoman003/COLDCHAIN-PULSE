import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, Handoff, Role, Shipment, TelemetryLog, User, utcnow
from ..security import require_roles
from ..services import integrity

router = APIRouter(prefix="/reports", tags=["compliance & audit"])
READERS = (Role.admin, Role.dispatcher, Role.auditor)


def _load(db: Session, shipment_id: int):
    s = db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(404, "Shipment not found")
    tele = db.scalars(select(TelemetryLog).where(TelemetryLog.shipment_id == s.id).order_by(TelemetryLog.id)).all()
    hand = db.scalars(select(Handoff).where(Handoff.shipment_id == s.id).order_by(Handoff.id)).all()
    alerts = db.scalars(select(Alert).where(Alert.shipment_id == s.id).order_by(Alert.created_at, Alert.id)).all()
    return s, tele, hand, alerts


def _integrity(s, tele, hand):
    t = integrity.verify_chain(tele, integrity.telemetry_payload)
    h = integrity.verify_chain(hand, integrity.handoff_payload)
    # Also compare the chain head with the one stored on the shipment (catches deleted tail rows)
    t["matches_shipment_head"] = t["head"] == s.telemetry_head
    h["matches_shipment_head"] = h["head"] == s.handoff_head
    ok = t["valid"] and h["valid"] and t["matches_shipment_head"] and h["matches_shipment_head"]
    return {"tamper_free": ok, "telemetry": t, "handoffs": h}


def _summary(s, tele, hand, alerts, integ) -> dict:
    temps = [r.temperature for r in tele]
    breaches = [a for a in alerts if a.level == "critical"]
    return {
        "shipment_code": s.code, "status": s.status, "origin": s.origin, "destination": s.destination,
        "product": s.product, "threshold_c": [s.min_temp, s.max_temp],
        "readings": len(tele), "min_c": min(temps) if temps else None, "max_c": max(temps) if temps else None,
        "avg_c": round(sum(temps) / len(temps), 2) if temps else None,
        "out_of_range_readings": sum(1 for x in temps if x < s.min_temp or x > s.max_temp),
        "sla_breaches": len(breaches), "compromised": s.compromised,
        "telemetry_chain_head": integ["telemetry"]["head"], "handoff_chain_head": integ["handoffs"]["head"],
        "tamper_free": integ["tamper_free"],
    }


@router.get("/shipments/{shipment_id}/verify")
def verify(shipment_id: int, _: User = Depends(require_roles(*READERS)), db: Session = Depends(get_db)):
    s, tele, hand, _a = _load(db, shipment_id)
    return {"shipment_code": s.code, **_integrity(s, tele, hand)}


@router.get("/shipments/{shipment_id}.csv")
def report_csv(shipment_id: int, _: User = Depends(require_roles(*READERS)), db: Session = Depends(get_db)):
    s, tele, hand, alerts = _load(db, shipment_id)
    integ = _integrity(s, tele, hand)
    summ = _summary(s, tele, hand, alerts, integ)
    generated = utcnow().isoformat()
    sig = integrity.sign_report({**summ, "generated_at": generated})
    buf = io.StringIO()
    w = csv.writer(buf)
    for k, v in summ.items():
        w.writerow([f"# {k}", v])
    w.writerow(["# generated_at_utc", generated])
    w.writerow(["# report_signature_hmac_sha256", sig])
    w.writerow([])
    w.writerow(["record_type", "timestamp_utc", "temperature_c", "humidity_pct", "detail", "record_hash"])
    for r in tele:
        w.writerow(["telemetry", r.recorded_at.isoformat(), r.temperature, r.humidity, "", r.hash])
    for h in hand:
        detail = f"{h.type} by user {h.user_id}; condition={h.condition}; gps={h.latitude},{h.longitude}; pin_verified={h.pin_verified}"
        w.writerow(["handoff", h.recorded_at.isoformat(), "", "", detail, h.hash])
    for a in alerts:
        w.writerow(["alert", a.created_at.isoformat(), a.temperature, "", f"{a.level}: {a.message}", ""])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{s.code}_audit.csv"'})


@router.get("/shipments/{shipment_id}.pdf")
def report_pdf(shipment_id: int, _: User = Depends(require_roles(*READERS)), db: Session = Depends(get_db)):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    s, tele, hand, alerts = _load(db, shipment_id)
    integ = _integrity(s, tele, hand)
    summ = _summary(s, tele, hand, alerts, integ)
    generated = utcnow().isoformat(timespec="seconds")
    sig = integrity.sign_report({**summ, "generated_at": generated})

    styles = getSampleStyleSheet()
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, title=f"Cold-chain audit {s.code}")
    grid = TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                       ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("FONTSIZE", (0, 0), (-1, -1), 7)])
    el = [Paragraph(f"Cold-Chain Compliance Report: {s.code}", styles["Title"]),
          Paragraph(f"{s.origin} → {s.destination} | product: {s.product or '-'} | status: {s.status}", styles["Normal"]),
          Paragraph(f"Allowed range: {s.min_temp}–{s.max_temp} °C | generated (UTC): {generated}", styles["Normal"]),
          Spacer(1, 10), Paragraph("Summary", styles["Heading2"])]
    rows = [["Readings", summ["readings"]], ["Min / Avg / Max °C", f"{summ['min_c']} / {summ['avg_c']} / {summ['max_c']}"],
            ["Out-of-range readings", summ["out_of_range_readings"]], ["SLA breaches (critical)", summ["sla_breaches"]],
            ["Shipment compromised", "YES" if s.compromised else "no"],
            ["Log integrity (hash chain)", "VERIFIED" if integ["tamper_free"] else "TAMPERING DETECTED"]]
    t = Table(rows, colWidths=[160, 300]); t.setStyle(grid); el += [t, Spacer(1, 8)]

    el.append(Paragraph("Chain-of-custody handoffs", styles["Heading2"]))
    hrows = [["Time (UTC)", "Type", "User", "Condition", "GPS", "PIN"]] + [
        [h.recorded_at.isoformat(timespec="seconds"), h.type, h.user_id, h.condition,
         f"{h.latitude},{h.longitude}", "yes" if h.pin_verified else "no"] for h in hand]
    t = Table(hrows, repeatRows=1); t.setStyle(grid); el += [t, Spacer(1, 8)]

    el.append(Paragraph("Alerts / SLA breaches", styles["Heading2"]))
    arows = [["Time (UTC)", "Level", "Message"]] + [[a.created_at.isoformat(timespec="seconds"), a.level, a.message[:90]] for a in alerts]
    t = Table(arows, repeatRows=1); t.setStyle(grid); el += [t, Spacer(1, 8)]

    el.append(Paragraph("Full temperature history", styles["Heading2"]))
    trows = [["Time (UTC)", "°C", "RH %", "Hash (first 16)"]] + [
        [r.recorded_at.isoformat(timespec="seconds"), r.temperature, r.humidity, r.hash[:16]] for r in tele]
    t = Table(trows, repeatRows=1); t.setStyle(grid); el += [t, Spacer(1, 8)]

    el += [Paragraph("Integrity", styles["Heading2"]),
           Paragraph(f"Telemetry chain head: {summ['telemetry_chain_head']}", styles["Code"]),
           Paragraph(f"Handoff chain head: {summ['handoff_chain_head']}", styles["Code"]),
           Paragraph(f"Report HMAC-SHA256: {sig}", styles["Code"])]
    doc.build(el)
    return Response(out.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{s.code}_audit.pdf"'})
