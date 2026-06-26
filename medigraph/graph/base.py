"""Graph backend interface.

Services never talk to Neo4j or NetworkX directly — they talk to a
``GraphBackend``. This is what lets MediGraph run identically whether the data
lives in an in-memory embedded graph (offline) or a live Neo4j AuraDB cluster.

The contract is deliberately *data-centric*: backends hydrate canonical
``PatientRecord`` objects, and the analytics/decision-support layers compute on
those uniformly. That keeps a single source of truth for clinical logic instead
of re-implementing it once in Python and once in Cypher.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from medigraph.domain.models import Patient, PatientRecord, Provider


class NotSupportedError(RuntimeError):
    """Raised when a backend cannot service a particular operation."""


@dataclass
class GraphStats:
    node_counts: Dict[str, int] = field(default_factory=dict)
    relationship_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def total_nodes(self) -> int:
        return sum(self.node_counts.values())

    @property
    def total_relationships(self) -> int:
        return sum(self.relationship_counts.values())


class GraphBackend(ABC):
    """Abstract knowledge-graph backend."""

    name: str = "abstract"
    is_live: bool = False

    # ---- Inventory --------------------------------------------------------
    @abstractmethod
    def stats(self) -> GraphStats:
        ...

    @abstractmethod
    def list_patients(self, limit: Optional[int] = None) -> List[Patient]:
        ...

    @abstractmethod
    def get_patient(self, patient_id: str) -> Optional[Patient]:
        ...

    @abstractmethod
    def get_patient_record(self, patient_id: str) -> Optional[PatientRecord]:
        ...

    @abstractmethod
    def all_patient_records(self) -> List[PatientRecord]:
        ...

    @abstractmethod
    def get_providers(self) -> List[Provider]:
        ...

    # ---- Search -----------------------------------------------------------
    def search_patients_by_name(self, query: str, limit: int = 25) -> List[Patient]:
        q = query.strip().lower()
        out = [p for p in self.list_patients() if q in p.full_name.lower() or q == p.id.lower()]
        return out[:limit]

    # ---- Visualisation ----------------------------------------------------
    @abstractmethod
    def subgraph_elements(
        self, patient_ids: Optional[List[str]] = None, limit: int = 75
    ) -> Tuple[List[dict], List[dict]]:
        """Return (nodes, edges) dicts suitable for a network visualisation."""
        ...

    # ---- Advanced / live-only --------------------------------------------
    def run_readonly_cypher(self, cypher: str) -> Tuple[List[str], List[list]]:
        """Execute a *validated, read-only* Cypher query. Embedded backends
        translate a structured plan instead and may raise NotSupportedError."""
        raise NotSupportedError(
            "Raw Cypher is only available with the live Neo4j backend. "
            "The offline backend answers questions via the structured planner."
        )

    def close(self) -> None:  # pragma: no cover - default no-op
        pass
