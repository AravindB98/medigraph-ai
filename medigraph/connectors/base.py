"""Pluggable connector framework.

Every external system MediGraph talks to — a FHIR server, an HL7 v2 feed, a
C-CDA document, a CSV extract, a warehouse — is wrapped in a ``BaseConnector``
that maps the source into the canonical ``PatientRecord``. Connectors register
themselves in a registry so new integrations are drop-in: add a module, decorate
the class, and it becomes discoverable to the UI/API without touching core code.

This is what makes the platform *vendor-neutral*: the clinical features never
know whether a patient came from Epic in Ohio or an ABDM-linked hospital in
Bengaluru.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Type

from medigraph.domain.models import PatientRecord


class Standard(str, Enum):
    FHIR_R4 = "HL7 FHIR R4"
    HL7_V2 = "HL7 v2.x"
    CCDA = "C-CDA (CDA R2)"
    X12 = "X12 EDI"
    CSV = "CSV / flat file"
    PROPRIETARY = "Vendor API"
    GRAPH = "Property graph"


class Direction(str, Enum):
    READ = "read"
    WRITE = "write"
    BIDIRECTIONAL = "bidirectional"


class Status(str, Enum):
    SUPPORTED = "supported"        # works out of the box (incl. offline sample)
    CONFIG = "config"             # implemented; needs credentials/endpoint
    ROADMAP = "roadmap"           # documented integration path


@dataclass
class ConnectorInfo:
    key: str
    name: str
    standard: Standard
    direction: Direction
    status: Status
    description: str = ""
    countries: List[str] = field(default_factory=lambda: ["US", "IN"])


class BaseConnector(ABC):
    """Abstract source/target connector."""

    info: ConnectorInfo

    @abstractmethod
    def test_connection(self) -> str:
        """Return a human-readable connection status (raises on hard failure)."""

    def fetch_record(self, patient_id: str) -> Optional[PatientRecord]:
        """Fetch a single patient as a canonical record (read connectors)."""
        raise NotImplementedError(f"{self.info.key} does not support single-record fetch.")

    def fetch_all(self, limit: Optional[int] = None) -> List[PatientRecord]:
        """Bulk fetch (optional)."""
        raise NotImplementedError(f"{self.info.key} does not support bulk fetch.")

    def ingest(self, payload) -> PatientRecord:
        """Parse an external payload (bundle/message/document) into a record."""
        raise NotImplementedError(f"{self.info.key} does not support ingest.")

    def export(self, record: PatientRecord):
        """Render a canonical record into the connector's external format."""
        raise NotImplementedError(f"{self.info.key} does not support export.")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: Dict[str, Type[BaseConnector]] = {}


def register(key: str) -> Callable[[Type[BaseConnector]], Type[BaseConnector]]:
    def _wrap(cls: Type[BaseConnector]) -> Type[BaseConnector]:
        _REGISTRY[key] = cls
        return cls
    return _wrap


def available_connectors() -> List[str]:
    return sorted(_REGISTRY.keys())


def get_connector(key: str, **kwargs) -> BaseConnector:
    if key not in _REGISTRY:
        raise KeyError(f"Unknown connector '{key}'. Available: {available_connectors()}")
    return _REGISTRY[key](**kwargs)


def connector_class(key: str) -> Type[BaseConnector]:
    return _REGISTRY[key]
