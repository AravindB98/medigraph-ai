"""Graph backend factory.

``get_graph()`` returns a process-wide backend chosen from settings: the live
Neo4j backend when credentials are present and selected, otherwise the embedded
offline graph. Falls back gracefully to embedded if a live connection fails, so
the app never hard-crashes on a bad credential.
"""
from __future__ import annotations

from typing import Optional

from medigraph.config import get_settings
from medigraph.graph.base import GraphBackend, GraphStats, NotSupportedError

_BACKEND: Optional[GraphBackend] = None


def get_graph(force_reload: bool = False) -> GraphBackend:
    global _BACKEND
    if _BACKEND is not None and not force_reload:
        return _BACKEND

    settings = get_settings()
    if settings.graph_is_live:
        try:
            from medigraph.graph.neo4j_backend import Neo4jGraph

            _BACKEND = Neo4jGraph()
            # Touch the connection so misconfig fails fast and we can fall back.
            _BACKEND.stats()
            return _BACKEND
        except Exception as exc:  # pragma: no cover - network dependent
            import warnings

            warnings.warn(f"Neo4j backend unavailable ({exc}); using embedded graph.")

    from medigraph.graph.embedded import EmbeddedGraph

    _BACKEND = EmbeddedGraph()
    return _BACKEND


def reset_graph() -> None:
    global _BACKEND
    if _BACKEND is not None:
        _BACKEND.close()
    _BACKEND = None


__all__ = ["get_graph", "reset_graph", "GraphBackend", "GraphStats", "NotSupportedError"]
