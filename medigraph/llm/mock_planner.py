"""Deterministic offline planner.

Generates simple read-only Cypher for the most common question shapes using
templates — no API key, no network, fully reproducible. For anything it can't
template, it raises so the caller can fall back to the structured planner rather
than fabricate a query.
"""
from __future__ import annotations

import re

from medigraph.llm.base import Planner


class MockPlanner(Planner):
    name = "mock"
    is_live = False

    def generate_cypher(self, question: str) -> str:
        ql = question.lower().strip()

        m = re.search(r"patients?\s+(with|who have)\s+([a-z0-9 ]+)", ql)
        if m:
            term = m.group(2).strip().split(" not ")[0].strip()
            return (
                "MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) "
                f"WHERE toLower(c.name) CONTAINS toLower('{term}') "
                "RETURN p.full_name AS patient, c.name AS condition LIMIT 100"
            )
        if "how many patients" in ql:
            m2 = re.search(r"(with|have)\s+([a-z0-9 ]+)", ql)
            term = m2.group(2).strip() if m2 else ""
            return (
                "MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) "
                f"WHERE toLower(c.name) CONTAINS toLower('{term}') "
                "RETURN count(DISTINCT p) AS patient_count"
            )
        if "most common" in ql and "condition" in ql:
            return (
                "MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) "
                "RETURN c.name AS condition, count(*) AS patients "
                "ORDER BY patients DESC LIMIT 10"
            )
        raise NotImplementedError(
            "Offline planner has no template for this question; using the structured planner."
        )
