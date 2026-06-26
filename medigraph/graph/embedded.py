"""Embedded knowledge-graph backend (NetworkX + bundled CSVs).

This is the **default, zero-credential** backend. On first use it loads the
bundled synthetic CSVs (generating them if missing) into canonical
``PatientRecord`` objects held in memory, and exposes the same interface as the
live Neo4j backend.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from medigraph.config import DATA_DIR
from medigraph.domain.models import (
    ConditionInstance,
    Encounter,
    EncounterClass,
    MedicationInstance,
    ObservationInstance,
    Patient,
    PatientRecord,
    Provider,
    Sex,
)
from medigraph.graph import analysis
from medigraph.graph.base import GraphBackend, GraphStats


def _parse_date(value) -> Optional[date]:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None


def _parse_dt(value) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


class EmbeddedGraph(GraphBackend):
    name = "embedded"
    is_live = False

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self._records: Dict[str, PatientRecord] = {}
        self._providers: Dict[str, Provider] = {}
        self._load()

    # ---- Loading ----------------------------------------------------------
    def _ensure_data(self) -> None:
        if not (self.data_dir / "patients.csv").exists():
            from medigraph.data.generator import generate

            generate()

    def _load(self) -> None:
        self._ensure_data()
        d = self.data_dir
        patients = pd.read_csv(d / "patients.csv", dtype=str)
        providers = pd.read_csv(d / "providers.csv", dtype=str)
        conditions = pd.read_csv(d / "conditions.csv", dtype=str)
        medications = pd.read_csv(d / "medications.csv", dtype=str)
        encounters = pd.read_csv(d / "encounters.csv", dtype=str)
        observations = pd.read_csv(d / "observations.csv", dtype=str)

        for _, r in providers.iterrows():
            self._providers[r["id"]] = Provider(
                id=r["id"], name=r["name"], specialty=_clean(r.get("specialty")) or "General Practice",
                npi=_clean(r.get("npi")), hpr_id=_clean(r.get("hpr_id")),
                organization=_clean(r.get("organization")), state=_clean(r.get("state")),
                country=_clean(r.get("country")) or "US")

        cond_by_pat = self._group(conditions, "patient_id")
        med_by_pat = self._group(medications, "patient_id")
        enc_by_pat = self._group(encounters, "patient_id")
        obs_by_pat = self._group(observations, "patient_id")

        for _, r in patients.iterrows():
            pid = r["id"]
            patient = Patient(
                id=pid, full_name=r["full_name"],
                sex=Sex(r["sex"]) if r.get("sex") in Sex._value2member_map_ else Sex.unknown,
                birth_date=_parse_date(r.get("birth_date")),
                age=int(r["age"]) if _clean(r.get("age")) else None,
                city=_clean(r.get("city")), state=_clean(r.get("state")),
                country=_clean(r.get("country")) or "US",
                mrn=_clean(r.get("mrn")), abha_id=_clean(r.get("abha_id")),
                primary_provider_id=_clean(r.get("primary_provider_id")))

            conditions_l = [
                ConditionInstance(
                    code_key=c["code_key"], name=c["name"], snomed=_clean(c.get("snomed")),
                    icd10=_clean(c.get("icd10")), clinical_status=_clean(c.get("clinical_status")) or "active",
                    onset_date=_parse_date(c.get("onset_date")))
                for c in cond_by_pat.get(pid, [])
            ]
            meds_l = [
                MedicationInstance(
                    code_key=m["code_key"], name=m["name"], rxnorm=_clean(m.get("rxnorm")),
                    drug_class=_clean(m.get("drug_class")), status=_clean(m.get("status")) or "active",
                    start_date=_parse_date(m.get("start_date")))
                for m in med_by_pat.get(pid, [])
            ]
            encs_l = [
                Encounter(
                    id=e["id"],
                    encounter_class=EncounterClass(e["encounter_class"])
                    if e.get("encounter_class") in EncounterClass._value2member_map_ else EncounterClass.ambulatory,
                    start=_parse_dt(e.get("start")), end=_parse_dt(e.get("end")),
                    provider_id=_clean(e.get("provider_id")), reason=_clean(e.get("reason")),
                    length_of_stay_days=int(e["length_of_stay_days"]) if _clean(e.get("length_of_stay_days")) else 0,
                    via_emergency=str(e.get("via_emergency")).lower() == "true")
                for e in enc_by_pat.get(pid, [])
            ]
            obs_l = [
                ObservationInstance(
                    code_key=o["code_key"], name=o["name"], loinc=_clean(o.get("loinc")),
                    value=float(o["value"]) if _clean(o.get("value")) else None,
                    unit=_clean(o.get("unit")), category=_clean(o.get("category")) or "laboratory",
                    effective_datetime=_parse_dt(o.get("effective_datetime")),
                    encounter_id=_clean(o.get("encounter_id")),
                    interpretation=_clean(o.get("interpretation")))
                for o in obs_by_pat.get(pid, [])
            ]
            provs = []
            if patient.primary_provider_id and patient.primary_provider_id in self._providers:
                provs.append(self._providers[patient.primary_provider_id])
            for e in encs_l:
                if e.provider_id and e.provider_id in self._providers:
                    pr = self._providers[e.provider_id]
                    if pr not in provs:
                        provs.append(pr)

            self._records[pid] = PatientRecord(
                patient=patient, conditions=conditions_l, medications=meds_l,
                encounters=encs_l, observations=obs_l, providers=provs)

    @staticmethod
    def _group(df: pd.DataFrame, key: str) -> Dict[str, List[dict]]:
        out: Dict[str, List[dict]] = {}
        for _, row in df.iterrows():
            out.setdefault(row[key], []).append(row.to_dict())
        return out

    # ---- Interface --------------------------------------------------------
    def stats(self) -> GraphStats:
        records = list(self._records.values())
        node_counts = {
            "Patient": len(records),
            "Provider": len(self._providers),
            "Encounter": sum(len(r.encounters) for r in records),
            "Condition": sum(len(r.conditions) for r in records),
            "Medication": sum(len(r.medications) for r in records),
            "Observation": sum(len(r.observations) for r in records),
        }
        rel_counts = {
            "HAS_ENCOUNTER": sum(len(r.encounters) for r in records),
            "HAS_CONDITION": sum(len(r.conditions) for r in records),
            "TAKES_MEDICATION": sum(len(r.medications) for r in records),
            "HAS_OBSERVATION": sum(len(r.observations) for r in records),
            "HAS_PROVIDER": sum(len(r.providers) for r in records),
        }
        return GraphStats(node_counts=node_counts, relationship_counts=rel_counts)

    def list_patients(self, limit: Optional[int] = None) -> List[Patient]:
        patients = [r.patient for r in self._records.values()]
        return patients[:limit] if limit else patients

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        rec = self._records.get(patient_id)
        return rec.patient if rec else None

    def get_patient_record(self, patient_id: str) -> Optional[PatientRecord]:
        return self._records.get(patient_id)

    def all_patient_records(self) -> List[PatientRecord]:
        return list(self._records.values())

    def get_providers(self) -> List[Provider]:
        return list(self._providers.values())

    def subgraph_elements(
        self, patient_ids: Optional[List[str]] = None, limit: int = 75
    ) -> Tuple[List[dict], List[dict]]:
        if patient_ids:
            records = [self._records[p] for p in patient_ids if p in self._records]
        else:
            records = list(self._records.values())
        return analysis.subgraph_elements(records, limit=limit)
