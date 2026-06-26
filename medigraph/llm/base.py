"""LLM planner interface.

The platform only uses an LLM in two narrow, *guard-railed* roles:
  1. translate a natural-language question into read-only Cypher, and
  2. produce a short natural-language summary of already-retrieved graph facts.

Keeping the surface this small is deliberate: the clinical logic stays
deterministic and auditable, and the LLM never has write access.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

# Shared schema description so any planner emits Cypher against the real graph.
SCHEMA_HINT = """
Neo4j schema:
Nodes:
- Patient(id, full_name, sex, age, city, state, country)
- Encounter(id, encounter_class, start, end)
- Condition(code_key, name, snomed, icd10)
- Medication(code_key, name, rxnorm, drug_class)
- Provider(id, name, specialty, npi)
- Observation(code_key, name, loinc, value, unit, category)
Relationships:
- (Patient)-[:HAS_ENCOUNTER]->(Encounter)
- (Patient)-[:HAS_CONDITION]->(Condition)
- (Patient)-[:TAKES_MEDICATION]->(Medication)
- (Patient)-[:HAS_PROVIDER]->(Provider)
- (Patient)-[:HAS_OBSERVATION]->(Observation)
Rules:
- Read-only queries ONLY (MATCH/WITH/RETURN). Never CREATE/MERGE/DELETE/SET.
- Filter names case-insensitively: WHERE toLower(c.name) CONTAINS toLower('diabetes')
- Return tabular results. No APOC. Output pure Cypher with no markdown.
"""


class Planner(ABC):
    name: str = "abstract"
    is_live: bool = False

    @abstractmethod
    def generate_cypher(self, question: str) -> str:
        ...

    def summarize(self, question: str, facts: str) -> str:  # optional
        return facts
