"""Alert engine: per-shipment state machine  ok -> warning -> critical.

* WARNING  : temperature within `warning_margin_c` of a limit, OR just went out of range
* CRITICAL : continuously out of range for >= `critical_breach_minutes`
  (measured with the sensors' own timestamps, so late offline-synced data is handled right)
An alert fires only on an upward state transition, so a long excursion creates
exactly 1 warning + 1 critical (no alert spam / false positives).
"""
from datetime import timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Alert, AlertLevel, Shipment, ShipmentStatus, TelemetryLog


def apply_reading(db: Session, s: Shipment, r: TelemetryLog) -> list[Alert]:
    # Out-of-order (older than what we already processed) readings are stored but don't move state.
    if s.last_reading_at and r.recorded_at < s.last_reading_at:
        return []
    s.last_temp, s.last_humidity, s.last_reading_at = r.temperature, r.humidity, r.recorded_at
    if s.status != ShipmentStatus.in_transit.value:
        return []

    created: list[Alert] = []
    lo, hi = s.min_temp, s.max_temp
    t = r.temperature
    out = t < lo or t > hi
    near = (not out) and (t - lo <= settings.warning_margin_c or hi - t <= settings.warning_margin_c)

    def fire(level: AlertLevel, msg: str):
        a = Alert(shipment_id=s.id, level=level.value, message=msg, temperature=t,
                  breach_started_at=s.breach_started_at, created_at=r.recorded_at)
        db.add(a)
        created.append(a)

    if out:
        if s.breach_started_at is None:
            s.breach_started_at = r.recorded_at
        minutes = (r.recorded_at - s.breach_started_at) / timedelta(minutes=1)
        if minutes >= settings.critical_breach_minutes:
            if s.alert_state != "critical":
                s.alert_state, s.compromised = "critical", True
                fire(AlertLevel.critical,
                     f"CRITICAL: {s.code} out of range ({lo}-{hi}°C) for {minutes:.0f} min, now {t:.1f}°C")
        elif s.alert_state == "ok":
            s.alert_state = "warning"
            fire(AlertLevel.warning, f"WARNING: {s.code} left safe range ({lo}-{hi}°C), now {t:.1f}°C")
    else:
        s.breach_started_at = None
        if near:
            if s.alert_state == "ok":
                s.alert_state = "warning"
                fire(AlertLevel.warning, f"WARNING: {s.code} approaching limit ({lo}-{hi}°C), now {t:.1f}°C")
            elif s.alert_state == "critical":
                s.alert_state = "warning"  # recovered, but still close to a limit
        else:
            s.alert_state = "ok"
    return created
