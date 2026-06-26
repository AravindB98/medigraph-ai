"""Service facade.

``ClinicalEngine`` is the single entry point the UI and API use. It wires a graph
backend to the clinical services and pins a consistent "as-of" anchor (the most
recent observation in the dataset) so that time-relative logic — overdue labs,
recent vitals — is stable and reproducible regardless of wall-clock time.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import pandas as pd

from medigraph.domain.models import PatientRecord
from medigraph.graph import get_graph
from medigraph.graph.analysis import latest_observation_datetime, provider_centrality
from medigraph.graph.base import GraphBackend, GraphStats
from medigraph.services import analytics, cohort, fhir, nlp, qa
from medigraph.services import decision_support as ds


class ClinicalEngine:
    def __init__(self, graph: Optional[GraphBackend] = None):
        self.graph = graph or get_graph()
        self._anchor: Optional[datetime] = None

    # ---- anchor -----------------------------------------------------------
    @property
    def as_of(self) -> datetime:
        if self._anchor is None:
            self._anchor = latest_observation_datetime(self.graph.all_patient_records()) or datetime.utcnow()
        return self._anchor

    # ---- inventory --------------------------------------------------------
    def stats(self) -> GraphStats:
        return self.graph.stats()

    def list_patients(self, limit: Optional[int] = None):
        return self.graph.list_patients(limit=limit)

    def record(self, patient_id: str) -> Optional[PatientRecord]:
        return self.graph.get_patient_record(patient_id)

    def search_patients(self, query: str, limit: int = 25):
        return self.graph.search_patients_by_name(query, limit=limit)

    def all_records(self) -> List[PatientRecord]:
        return self.graph.all_patient_records()

    # ---- decision support -------------------------------------------------
    def assess(self, patient_id: str) -> Optional[ds.PatientAssessment]:
        rec = self.record(patient_id)
        if not rec:
            return None
        return ds.assess_patient(rec, as_of=self.as_of)

    # ---- population health ------------------------------------------------
    def population_summary(self) -> dict:
        return analytics.population_summary(self.all_records())

    def condition_prevalence(self) -> pd.DataFrame:
        return analytics.condition_prevalence(self.all_records())

    def medication_usage(self) -> pd.DataFrame:
        return analytics.medication_usage(self.all_records())

    def utilization(self) -> dict:
        return analytics.utilization(self.all_records())

    def quality_measures(self) -> List[analytics.QualityMeasure]:
        return analytics.quality_measures(self.all_records(), as_of=self.as_of)

    def risk_stratification(self) -> dict:
        return analytics.risk_stratification(self.all_records(), as_of=self.as_of)

    def top_priority_patients(self, limit: int = 15) -> pd.DataFrame:
        return analytics.top_priority_patients(self.all_records(), as_of=self.as_of, limit=limit)

    def provider_centrality(self) -> pd.DataFrame:
        return provider_centrality(self.all_records())

    # ---- cohorts ----------------------------------------------------------
    def build_cohort(self, criteria: cohort.CohortCriteria) -> cohort.CohortResult:
        return cohort.build_cohort(self.all_records(), criteria)

    def preset_registries(self):
        return cohort.preset_registries()

    # ---- Q&A and NLP ------------------------------------------------------
    def ask(self, question: str) -> qa.QAResult:
        return qa.answer(question, self.graph)

    def analyze_note(self, text: str) -> nlp.NoteAnalysis:
        return nlp.analyze_note(text)

    # ---- FHIR -------------------------------------------------------------
    def to_fhir(self, patient_id: str) -> Optional[dict]:
        rec = self.record(patient_id)
        return fhir.record_to_bundle(rec) if rec else None

    def import_fhir(self, bundle: dict) -> PatientRecord:
        return fhir.bundle_to_record(bundle)

    # ---- viz --------------------------------------------------------------
    def subgraph_elements(self, patient_ids=None, limit: int = 75):
        return self.graph.subgraph_elements(patient_ids=patient_ids, limit=limit)


_ENGINE: Optional[ClinicalEngine] = None


def get_engine(force_reload: bool = False) -> ClinicalEngine:
    global _ENGINE
    if _ENGINE is None or force_reload:
        _ENGINE = ClinicalEngine()
    return _ENGINE


__all__ = ["ClinicalEngine", "get_engine"]
