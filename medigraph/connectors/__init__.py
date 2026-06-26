"""Connector package.

Importing this package registers all bundled connectors so they are discoverable
via the registry (``available_connectors`` / ``get_connector``). Add a new module
that calls ``@register(...)`` and import it here to make it pluggable.
"""
from __future__ import annotations

from medigraph.connectors.base import (
    BaseConnector,
    ConnectorInfo,
    Direction,
    Standard,
    Status,
    available_connectors,
    connector_class,
    get_connector,
    register,
)

# Importing these modules triggers their @register decorators.
from medigraph.connectors import ccda, csv_connector, fhir_connector, hl7v2, snowflake_connector  # noqa: E402,F401

# Neo4j connector is optional/live; register a thin info entry lazily.
try:  # pragma: no cover - optional
    from medigraph.connectors import neo4j_connector  # noqa: F401
except Exception:
    pass

from medigraph.connectors.catalog import (  # noqa: E402
    CATALOG,
    CatalogEntry,
    catalog_by_country,
    catalog_summary,
)


def connector_directory() -> list[dict]:
    """Return registered connectors with their metadata (for UI/API)."""
    out = []
    for key in available_connectors():
        cls = connector_class(key)
        info = getattr(cls, "info", None)
        if info is None:
            continue
        out.append({
            "key": info.key, "name": info.name, "standard": info.standard.value,
            "direction": info.direction.value, "status": info.status.value,
            "countries": info.countries, "description": info.description,
        })
    return out


__all__ = [
    "BaseConnector", "ConnectorInfo", "Direction", "Standard", "Status",
    "register", "get_connector", "available_connectors", "connector_class",
    "connector_directory", "CATALOG", "CatalogEntry", "catalog_by_country",
    "catalog_summary",
]
