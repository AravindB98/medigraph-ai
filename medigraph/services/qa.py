"""GraphRAG question answering — grounded, cited, and safe.

A deterministic natural-language planner that maps clinical questions onto graph
retrievals and always returns:

- a written answer,
- the supporting rows (a DataFrame), and
- **citations** — the exact graph entities the answer was derived from.

Design principles:
- **Grounded only.** Answers come from graph facts, never free-form generation.
- **Safe by default.** Unsupported questions get an honest "I can't answer that
  from the graph" instead of a hallucination.
- **Optionally LLM-assisted.** With a live Neo4j backend + OpenAI key, a question
  the planner can't handle is escalated to an LLM that proposes Cypher, which is
  then passed through the read-only guard before execution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import pandas as pd

from medigraph.domain import terminology as T
from medigraph.graph.base import GraphBackend
from medigraph.services import decision_support as ds


@dataclass
class QAResult:
    answer: str
    data: Optional[pd.DataFrame] = None
    citations: List[str] = field(default_factory=list)
    intent: str = "unknown"
    cypher: Optional[str] = None
    grounded: bool = True


def _find_condition_key(text: str) -> Optional[str]:
    syns = T.all_condition_synonyms()
    text = text.lower()
    # longest synonym first
    for phrase in sorted(syns, key=len, reverse=True):
        if re.search(r"\b" + re.escape(phrase) + r"\b", text):
            return syns[phrase]
    return None


def _find_patient(graph: GraphBackend, token: str):
    token = token.strip()
    rec = graph.get_patient_record(token)
    if rec:
        return rec
    matches = graph.search_patients_by_name(token, limit=1)
    if matches:
        return graph.get_patient_record(matches[0].id)
    return None


def _anchor(graph: GraphBackend) -> datetime:
    from medigraph.graph.analysis import latest_observation_datetime

    return latest_observation_datetime(graph.all_patient_records()) or datetime.utcnow()


SUPPORTED_HELP = (
    "I can answer questions grounded in the knowledge graph, e.g.:\n"
    "• show patients with diabetes\n"
    "• how many patients have hypertension\n"
    "• medications for patient <name or id>\n"
    "• care gaps for patient <name or id>\n"
    "• drug interactions for patient <name or id>\n"
    "• patients with atrial fibrillation not on anticoagulant\n"
    "• most common conditions"
)


def answer(question: str, graph: GraphBackend) -> QAResult:
    if not question or not question.strip():
        return QAResult("Please enter a question.", grounded=False, intent="empty")
    q = question.strip()
    ql = q.lower()

    # --- prevalence / most common conditions ---
    if re.search(r"\b(most common|top|prevalence|common)\b.*\bcondition", ql):
        from medigraph.services.analytics import condition_prevalence

        df = condition_prevalence(graph.all_patient_records()).head(10)
        return QAResult("Most common conditions across the population:", df,
                        citations=[f"Condition/{r}" for r in df['condition'].tolist()],
                        intent="prevalence")

    # --- count patients with condition ---
    m = re.search(r"how many patients?.*\b(with|have|having)\b\s+(.+)", ql)
    if m:
        key = _find_condition_key(m.group(2))
        if key:
            recs = [r for r in graph.all_patient_records() if key in r.condition_keys]
            name = T.CONDITIONS[key].name
            return QAResult(f"**{len(recs)}** patients have {name}.",
                            pd.DataFrame([{"condition": name, "patient_count": len(recs)}]),
                            citations=[f"Patient/{r.patient.id}" for r in recs[:50]],
                            intent="count_condition")

    # --- care gaps for patient ---
    m = re.search(r"(care gaps?|gaps?)\s+(for|of)\s+patient\s+(.+)", ql)
    if m:
        rec = _find_patient(graph, m.group(3))
        if rec:
            a = ds.assess_patient(rec, as_of=_anchor(graph))
            if not a.care_gaps:
                return QAResult(f"No open care gaps detected for **{rec.patient.full_name}**.",
                                intent="care_gaps", citations=[f"Patient/{rec.patient.id}"])
            df = pd.DataFrame([{"gap": g.title, "severity": g.severity,
                                "recommendation": g.recommendation, "guideline": g.guideline}
                               for g in a.care_gaps])
            return QAResult(f"Care gaps for **{rec.patient.full_name}**:", df,
                            citations=[f"Patient/{rec.patient.id}"], intent="care_gaps")
        return QAResult("I couldn't find that patient.", grounded=False, intent="care_gaps")

    # --- drug interactions for patient ---
    m = re.search(r"(drug )?interactions?\s+(for|of)\s+patient\s+(.+)", ql)
    if m:
        rec = _find_patient(graph, m.group(3))
        if rec:
            alerts = ds.detect_interactions(rec)
            if not alerts:
                return QAResult(f"No known drug–drug interactions for **{rec.patient.full_name}**.",
                                intent="interactions", citations=[f"Patient/{rec.patient.id}"])
            df = pd.DataFrame([{"drug_a": a.drug_a, "drug_b": a.drug_b,
                                "severity": a.severity, "management": a.management} for a in alerts])
            return QAResult(f"Drug interactions for **{rec.patient.full_name}**:", df,
                            citations=[f"Patient/{rec.patient.id}"], intent="interactions")

    # --- cohort: condition NOT on medication ---
    m = re.search(r"patients? with (.+?) (not on|without)\s+(.+)", ql)
    if m:
        ckey = _find_condition_key(m.group(1))
        med_phrase = m.group(3)
        med_key = T.all_medication_synonyms().get(med_phrase.strip())
        klass = None
        if "anticoag" in med_phrase:
            klass = {"warfarin", "apixaban"}
        elif "statin" in med_phrase:
            klass = {"atorvastatin"}
        if ckey:
            recs = []
            for r in graph.all_patient_records():
                if ckey not in r.condition_keys:
                    continue
                meds = set(r.medication_keys)
                if klass and not (meds & klass):
                    recs.append(r)
                elif med_key and med_key not in meds:
                    recs.append(r)
            df = pd.DataFrame([{"patient_id": r.patient.id, "name": r.patient.full_name,
                                "age": r.patient.age} for r in recs])
            return QAResult(
                f"**{len(recs)}** patients with {T.CONDITIONS[ckey].name} are not on {med_phrase}.",
                df, citations=[f"Patient/{r.patient.id}" for r in recs[:50]], intent="cohort_gap")

    # --- medications for a condition ---
    m = re.search(r"(medications?|drugs?|treatments?)\s+for\s+(.+)", ql)
    if m and "patient" not in m.group(2):
        key = _find_condition_key(m.group(2))
        if key:
            meds = [mm for mm in T.MEDICATIONS.values() if key in mm.treats]
            df = pd.DataFrame([{"medication": mm.name, "drug_class": mm.drug_class,
                                "rxnorm": mm.rxnorm} for mm in meds])
            return QAResult(f"Medications commonly used for {T.CONDITIONS[key].name}:", df,
                            citations=[f"Medication/{mm.key}" for mm in meds], intent="meds_for_condition")

    # --- per-patient lookups: medications/conditions/observations/encounters/providers ---
    m = re.search(r"(medications?|conditions?|observations?|encounters?|providers?)\s+(for|of)\s+patient\s+(.+)", ql)
    if m:
        what = m.group(1)
        rec = _find_patient(graph, m.group(3))
        if not rec:
            return QAResult("I couldn't find that patient.", grounded=False, intent="patient_lookup")
        pid = rec.patient.id
        cite = [f"Patient/{pid}"]
        if what.startswith("medication"):
            df = pd.DataFrame([{"medication": x.name, "class": x.drug_class, "status": x.status}
                               for x in rec.medications])
            return QAResult(f"Medications for **{rec.patient.full_name}**:", df, cite, "patient_meds")
        if what.startswith("condition"):
            df = pd.DataFrame([{"condition": x.name, "icd10": x.icd10, "status": x.clinical_status}
                               for x in rec.conditions])
            return QAResult(f"Conditions for **{rec.patient.full_name}**:", df, cite, "patient_conditions")
        if what.startswith("observation"):
            df = pd.DataFrame([{"observation": x.name, "value": x.value, "unit": x.unit,
                                "interpretation": x.interpretation} for x in rec.observations[:50]])
            return QAResult(f"Observations for **{rec.patient.full_name}** (latest 50):", df, cite, "patient_obs")
        if what.startswith("encounter"):
            df = pd.DataFrame([{"encounter": x.id, "class": str(getattr(x.encounter_class, 'value', x.encounter_class)),
                                "reason": x.reason} for x in rec.encounters])
            return QAResult(f"Encounters for **{rec.patient.full_name}**:", df, cite, "patient_encounters")
        if what.startswith("provider"):
            df = pd.DataFrame([{"provider": p.name, "specialty": p.specialty} for p in rec.providers])
            return QAResult(f"Providers for **{rec.patient.full_name}**:", df, cite, "patient_providers")

    # --- patients with condition (generic) ---
    key = _find_condition_key(ql)
    if key and re.search(r"\b(patients?|show|list|who)\b", ql):
        recs = [r for r in graph.all_patient_records() if key in r.condition_keys]
        df = pd.DataFrame([{"patient_id": r.patient.id, "name": r.patient.full_name,
                            "age": r.patient.age, "country": r.patient.country} for r in recs])
        return QAResult(f"**{len(recs)}** patients with {T.CONDITIONS[key].name}:", df,
                        citations=[f"Patient/{r.patient.id}" for r in recs[:50]], intent="patients_with_condition")

    # --- escalate to LLM (live) or fall back ---
    escalated = _try_llm(question, graph)
    if escalated is not None:
        return escalated

    return QAResult(
        "I can't answer that from the knowledge graph yet. " + SUPPORTED_HELP,
        grounded=False, intent="unsupported")


def _try_llm(question: str, graph: GraphBackend) -> Optional[QAResult]:
    """If a live LLM + Cypher-capable backend are configured, propose & run Cypher."""
    from medigraph.config import get_settings

    settings = get_settings()
    if not settings.llm_is_live or not graph.is_live:
        return None
    try:
        from medigraph.llm import get_planner

        planner = get_planner()
        cypher = planner.generate_cypher(question)
        cols, rows = graph.run_readonly_cypher(cypher)
        df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
        return QAResult("Answer generated via LLM-proposed Cypher (read-only, validated):",
                        df, intent="llm_cypher", cypher=cypher)
    except Exception as exc:  # pragma: no cover - network dependent
        return QAResult(f"LLM/Cypher path could not complete safely: {exc}",
                        grounded=False, intent="llm_error")
