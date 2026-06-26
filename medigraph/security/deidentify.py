"""PHI de-identification (HIPAA Safe-Harbor flavoured).

Produces a de-identified copy of a PatientRecord suitable for analysts: direct
identifiers are removed or pseudonymised, ages over 89 are capped, and locations
are generalised. This lets the analyst role work on real distributions without
ever touching identifiable PHI — the same separation real research/analytics
teams operate under.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy

from medigraph.config import get_settings
from medigraph.domain.models import PatientRecord


def pseudonymize_id(value: str) -> str:
    settings = get_settings()
    digest = hashlib.sha256((settings.secret_key + "|" + value).encode()).hexdigest()
    return "deid-" + digest[:12]


def deidentify_record(record: PatientRecord) -> PatientRecord:
    rec = deepcopy(record)
    p = rec.patient
    pseudo = pseudonymize_id(p.id)

    p.id = pseudo
    p.full_name = f"Patient {pseudo[-6:]}"
    p.mrn = None
    p.abha_id = None
    p.birth_date = None
    # Safe-harbor: cap ages > 89 into a single bucket.
    if p.age is not None and p.age > 89:
        p.age = 90
    p.city = None  # generalise location to state/country only
    p.primary_provider_id = None

    # Strip provider identities; keep specialty for case-mix analysis.
    for prov in rec.providers:
        prov.name = "Provider (redacted)"
        prov.npi = None
        prov.hpr_id = None

    # Coarsen observation timestamps and drop encounter-level identifiers.
    for o in rec.observations:
        o.encounter_id = None
        if o.effective_datetime:
            o.effective_datetime = o.effective_datetime.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    for e in rec.encounters:
        e.id = pseudonymize_id(e.id)
        e.provider_id = None
        e.start = None
        e.end = None
    return rec
