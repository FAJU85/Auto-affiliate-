"""Base types shared by all sensors."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Severity(str, Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass
class Finding:
    sensor: str
    check: str
    severity: Severity
    message: str
    detail: str = ""
    fix_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "sensor": self.sensor,
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
            "detail": self.detail,
            "fix_hint": self.fix_hint,
        }


@dataclass
class SensorReport:
    sensor: str
    status: Severity = Severity.OK
    findings: list[Finding] = field(default_factory=list)
    duration_ms: float = 0.0
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add(self, check: str, severity: Severity, message: str,
            detail: str = "", fix_hint: str = "") -> None:
        f = Finding(self.sensor, check, severity, message, detail, fix_hint)
        self.findings.append(f)
        if severity == Severity.CRITICAL:
            self.status = Severity.CRITICAL
        elif severity == Severity.WARN and self.status == Severity.OK:
            self.status = Severity.WARN

    def to_dict(self) -> dict:
        return {
            "sensor": self.sensor,
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
            "duration_ms": round(self.duration_ms, 1),
            "ts": self.ts,
        }
