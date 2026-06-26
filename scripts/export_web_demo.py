"""Export a compact, real demo dataset for the static GitHub Pages site.

Everything in ``website/assets/data.json`` is produced by the *actual* MediGraph
engine (risk scores, care gaps, interactions, quality measures), so the
browser demo shows genuine platform output rather than hand-written mock-ups.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make the package importable when run as a script (e.g. in CI) without install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from medigraph.connectors import CATALOG  # noqa: E402
from medigraph.services import get_engine  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "website" / "assets" / "data.json"
MAX_PATIENTS = 48


def _obs(rec, key):
    o = rec.latest_observation(key)
    return round(o.value, 1) if o and o.value is not None else None


def build() -> dict:
    eng = get_engine()
    records = eng.all_records()

    patients = []
    for rec in records[:MAX_PATIENTS]:
        a = eng.assess(rec.patient.id)
        p = rec.patient
        patients.append({
            "id": p.id,
            "name": p.full_name,
            "age": p.age,
            "sex": p.sex.value,
            "country": p.country,
            "city": p.city,
            "conditions": [{"key": c.code_key, "name": c.name, "icd10": c.icd10} for c in rec.conditions],
            "medications": [{"key": m.code_key, "name": m.name} for m in rec.medications],
            "labs": {k: _obs(rec, k) for k in ["hba1c", "sbp", "dbp", "ldl", "egfr", "creatinine", "tsh", "hgb"]},
            "priority": round(a.priority_score, 1),
            "risk_scores": [{"name": s.name, "score": s.score, "band": s.risk_band,
                             "interpretation": s.interpretation, "unit": s.unit} for s in a.risk_scores],
            "care_gaps": [{"title": g.title, "severity": g.severity, "detail": g.detail,
                           "recommendation": g.recommendation, "guideline": g.guideline} for g in a.care_gaps],
            "interactions": [{"a": i.drug_a, "b": i.drug_b, "severity": i.severity,
                              "management": i.management} for i in a.interactions],
        })

    prevalence = eng.condition_prevalence().head(10).to_dict(orient="records")
    quality = [{"name": m.name, "rate": m.rate, "numerator": m.numerator,
                "denominator": m.denominator} for m in eng.quality_measures()]
    stats = eng.stats()
    rs = eng.risk_stratification()
    pop = eng.population_summary()

    catalog = [{"name": e.name, "country": e.country, "category": e.category,
                "standard": e.standard, "status": e.status, "notes": e.notes} for e in CATALOG]

    return {
        "meta": {
            "version": "2.0.0",
            "nodes": stats.total_nodes,
            "relationships": stats.total_relationships,
            "node_counts": stats.node_counts,
            "patients_total": len(records),
            "country_split": pop["country_split"],
        },
        "population": {
            "prevalence": prevalence,
            "quality": quality,
            "risk_bands": rs["lace_bands"],
            "total_care_gaps": rs["total_care_gaps"],
            "total_interactions": rs["total_interactions"],
        },
        "patients": sorted(patients, key=lambda x: x["priority"], reverse=True),
        "catalog": catalog,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Also emit a JS file so the static site works even when opened via file://
    # (no fetch/CORS needed). The site reads window.MEDIGRAPH_DATA.
    js = "window.MEDIGRAPH_DATA = " + json.dumps(data) + ";"
    OUT.with_name("data.js").write_text(js, encoding="utf-8")
    print(f"Wrote {OUT} and data.js ({OUT.stat().st_size//1024} KB) — {len(data['patients'])} patients, "
          f"{len(data['catalog'])} catalog entries.")


if __name__ == "__main__":
    main()
