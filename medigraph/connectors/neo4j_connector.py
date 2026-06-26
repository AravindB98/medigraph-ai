"""Neo4j graph connector (live).

Thin connector wrapper around the live Neo4j backend so the graph itself is a
first-class, registered integration in the catalog/registry.
"""
from __future__ import annotations

from typing import List, Optional

from medigraph.connectors.base import (
    BaseConnector,
    ConnectorInfo,
    Direction,
    Standard,
    Status,
    register,
)
from medigraph.domain.models import PatientRecord


@register("neo4j")
class Neo4jConnector(BaseConnector):
    info = ConnectorInfo(
        key="neo4j", name="Neo4j knowledge graph", standard=Standard.GRAPH,
        direction=Direction.BIDIRECTIONAL, status=Status.SUPPORTED,
        description="Live Neo4j AuraDB knowledge-graph backend.",
        countries=["US", "IN"])

    def __init__(self):
        from medigraph.graph.neo4j_backend import Neo4jGraph

        self._graph = Neo4jGraph()

    def test_connection(self) -> str:
        stats = self._graph.stats()
        return f"Connected to Neo4j — {stats.total_nodes} nodes, {stats.total_relationships} relationships."

    def fetch_all(self, limit: Optional[int] = None) -> List[PatientRecord]:
        recs = self._graph.all_patient_records()
        return recs[:limit] if limit else recs

    def fetch_record(self, patient_id: str) -> Optional[PatientRecord]:
        return self._graph.get_patient_record(patient_id)
