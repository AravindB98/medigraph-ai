"""CSV / flat-file connector.

Small clinics, registries and legacy systems frequently export flat files. This
connector loads MediGraph's bundled CSV schema (or a compatible export) into
canonical records by reusing the embedded loader — a reliable, offline path that
also doubles as the default data source.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from medigraph.config import DATA_DIR
from medigraph.connectors.base import (
    BaseConnector,
    ConnectorInfo,
    Direction,
    Standard,
    Status,
    register,
)
from medigraph.domain.models import PatientRecord


@register("csv")
class CSVConnector(BaseConnector):
    info = ConnectorInfo(
        key="csv", name="CSV / flat file", standard=Standard.CSV,
        direction=Direction.READ, status=Status.SUPPORTED,
        description="Loads the bundled/compatible CSV schema into the graph.",
        countries=["US", "IN"])

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR

    def test_connection(self) -> str:
        ok = (self.data_dir / "patients.csv").exists()
        return f"CSV source {'ready' if ok else 'missing'} at {self.data_dir}."

    def fetch_all(self, limit: Optional[int] = None) -> List[PatientRecord]:
        from medigraph.graph.embedded import EmbeddedGraph

        graph = EmbeddedGraph(data_dir=self.data_dir)
        recs = graph.all_patient_records()
        return recs[:limit] if limit else recs

    def fetch_record(self, patient_id: str) -> Optional[PatientRecord]:
        from medigraph.graph.embedded import EmbeddedGraph

        return EmbeddedGraph(data_dir=self.data_dir).get_patient_record(patient_id)
