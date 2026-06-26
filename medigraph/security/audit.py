"""Audit logging.

Every access to patient data and every clinical query is recorded as an
append-only JSONL event (actor, role, action, resource, outcome, timestamp).
This is the backbone of a HIPAA / India-DPDP accountability trail: *who saw or
did what, to which record, and when*. The log is append-only and easy to ship to
a SIEM.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from medigraph.config import get_settings

_LOCK = threading.Lock()


@dataclass
class AuditEvent:
    actor: str
    role: str
    action: str                       # e.g. "view_patient", "run_query", "export_fhir"
    resource: str = ""                # e.g. "Patient/pat-0001"
    patient_id: Optional[str] = None
    outcome: str = "success"          # success | denied | error
    detail: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def log_event(event: AuditEvent) -> None:
    settings = get_settings()
    settings.ensure_runtime_dir()
    line = json.dumps(asdict(event), ensure_ascii=False)
    with _LOCK:
        with settings.audit_log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def record(actor: str, role: str, action: str, resource: str = "",
           patient_id: Optional[str] = None, outcome: str = "success", detail: str = "") -> AuditEvent:
    ev = AuditEvent(actor=actor, role=role, action=action, resource=resource,
                    patient_id=patient_id, outcome=outcome, detail=detail)
    log_event(ev)
    return ev


def read_events(limit: int = 200) -> List[dict]:
    settings = get_settings()
    path: Path = settings.audit_log_path
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    out = []
    for line in lines[-limit:]:
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(out))
