"""Live Neo4j AuraDB backend.

Implements the same ``GraphBackend`` contract as the embedded graph by hydrating
canonical ``PatientRecord`` objects from Cypher. Importing this module does not
require the ``neo4j`` driver until the backend is actually instantiated, so the
offline install stays lightweight.

The schema matches the original MediGraph AI knowledge graph:
    (:Patient)-[:HAS_ENCOUNTER]->(:Encounter)
    (:Patient)-[:HAS_CONDITION]->(:Condition)
    (:Patient)-[:TAKES_MEDICATION]->(:Medication)
    (:Patient)-[:HAS_PROVIDER]->(:Provider)
    (:Patient)-[:HAS_OBSERVATION]->(:Observation)
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from medigraph.config import get_settings
from medigraph.domain.models import (
    ConditionInstance,
    Encounter,
    MedicationInstance,
    ObservationInstance,
    Patient,
    PatientRecord,
    Provider,
    Sex,
)
from medigraph.graph import analysis
from medigraph.graph.base import GraphBackend, GraphStats
from medigraph.graph.cypher_guard import validate


class Neo4jGraph(GraphBackend):
    name = "neo4j"
    is_live = True

    def __init__(self, uri=None, user=None, password=None, database=None):
        from neo4j import GraphDatabase  # imported lazily

        s = get_settings()
        self._database = database or s.neo4j_database
        self._driver = GraphDatabase.driver(
            uri or s.neo4j_uri, auth=(user or s.neo4j_user, password or s.neo4j_password)
        )
        self._cache: Optional[List[PatientRecord]] = None

    # ---- low level --------------------------------------------------------
    def _run(self, cypher: str, **params):
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, **params)
            records = [r.data() for r in result]
        return records

    # ---- interface --------------------------------------------------------
    def stats(self) -> GraphStats:
        node_rows = self._run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c"
        )
        rel_rows = self._run(
            "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c"
        )
        node_counts = {r["label"]: r["c"] for r in node_rows if r["label"]}
        rel_counts = {r["t"]: r["c"] for r in rel_rows}
        return GraphStats(node_counts=node_counts, relationship_counts=rel_counts)

    def _hydrate_all(self) -> List[PatientRecord]:
        if self._cache is not None:
            return self._cache
        rows = self._run(
            """
            MATCH (p:Patient)
            OPTIONAL MATCH (p)-[:HAS_CONDITION]->(c:Condition)
            OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)
            OPTIONAL MATCH (p)-[:HAS_PROVIDER]->(pr:Provider)
            OPTIONAL MATCH (p)-[:HAS_OBSERVATION]->(o:Observation)
            OPTIONAL MATCH (p)-[:HAS_ENCOUNTER]->(e:Encounter)
            RETURN p AS patient,
                   collect(DISTINCT c) AS conditions,
                   collect(DISTINCT m) AS medications,
                   collect(DISTINCT pr) AS providers,
                   collect(DISTINCT o) AS observations,
                   collect(DISTINCT e) AS encounters
            """
        )
        records = [self._row_to_record(r) for r in rows]
        self._cache = records
        return records

    @staticmethod
    def _row_to_record(row: dict) -> PatientRecord:
        p = row["patient"] or {}
        sex_val = (p.get("sex") or "unknown").lower()
        patient = Patient(
            id=str(p.get("id")), full_name=p.get("full_name") or p.get("name") or str(p.get("id")),
            sex=Sex(sex_val) if sex_val in Sex._value2member_map_ else Sex.unknown,
            age=p.get("age"), city=p.get("city"), state=p.get("state"),
            country=p.get("country") or "US", mrn=p.get("mrn"), abha_id=p.get("abha_id"),
            primary_provider_id=p.get("primary_provider_id"))
        conditions = [
            ConditionInstance(code_key=c.get("code") or c.get("code_key") or c.get("name", ""),
                              name=c.get("name", ""), snomed=c.get("snomed") or c.get("code"),
                              icd10=c.get("icd10"))
            for c in (row.get("conditions") or []) if c
        ]
        meds = [
            MedicationInstance(code_key=m.get("code") or m.get("code_key") or m.get("name", ""),
                               name=m.get("name", ""), rxnorm=m.get("rxnorm") or m.get("code"))
            for m in (row.get("medications") or []) if m
        ]
        providers = [
            Provider(id=str(pr.get("id")), name=pr.get("name", ""),
                     specialty=pr.get("specialty") or "General Practice",
                     npi=pr.get("npi"), state=pr.get("state"), country=pr.get("country") or "US")
            for pr in (row.get("providers") or []) if pr
        ]
        observations = [
            ObservationInstance(code_key=o.get("code_key") or o.get("code") or o.get("description", ""),
                                name=o.get("description") or o.get("name", ""),
                                loinc=o.get("loinc") or o.get("code"),
                                value=_to_float(o.get("value")), unit=o.get("unit"),
                                category=o.get("category") or "laboratory")
            for o in (row.get("observations") or []) if o
        ]
        encounters = []
        from medigraph.domain.models import EncounterClass

        for e in (row.get("encounters") or []):
            if not e:
                continue
            encounters.append(Encounter(
                id=str(e.get("id")), encounter_class=EncounterClass.ambulatory,
                provider_id=e.get("provider_npi") or e.get("provider_id"),
                length_of_stay_days=int(e.get("length_of_stay_days") or 0),
                via_emergency=bool(e.get("via_emergency"))))
        return PatientRecord(patient=patient, conditions=conditions, medications=meds,
                             providers=providers, observations=observations, encounters=encounters)

    def all_patient_records(self) -> List[PatientRecord]:
        return self._hydrate_all()

    def list_patients(self, limit: Optional[int] = None) -> List[Patient]:
        recs = self._hydrate_all()
        patients = [r.patient for r in recs]
        return patients[:limit] if limit else patients

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        rec = self.get_patient_record(patient_id)
        return rec.patient if rec else None

    def get_patient_record(self, patient_id: str) -> Optional[PatientRecord]:
        for r in self._hydrate_all():
            if r.patient.id == patient_id:
                return r
        return None

    def get_providers(self) -> List[Provider]:
        seen = {}
        for r in self._hydrate_all():
            for pr in r.providers:
                seen[pr.id] = pr
        return list(seen.values())

    def subgraph_elements(self, patient_ids=None, limit: int = 75) -> Tuple[List[dict], List[dict]]:
        recs = self._hydrate_all()
        if patient_ids:
            recs = [r for r in recs if r.patient.id in set(patient_ids)]
        return analysis.subgraph_elements(recs, limit=limit)

    def run_readonly_cypher(self, cypher: str) -> Tuple[List[str], List[list]]:
        result = validate(cypher)
        if not result.allowed:
            raise PermissionError(f"Blocked by read-only guard: {result.reason}")
        with self._driver.session(database=self._database) as session:
            res = session.run(result.normalized)
            records = list(res)
            keys = list(res.keys())
        rows = [[rec.get(k) for k in keys] for rec in records]
        return keys, rows

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception:
            pass


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
