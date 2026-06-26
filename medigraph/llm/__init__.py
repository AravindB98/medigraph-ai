"""Pluggable LLM planner: deterministic offline mock or live OpenAI."""
from __future__ import annotations

from typing import Optional

from medigraph.config import get_settings
from medigraph.llm.base import Planner

_PLANNER: Optional[Planner] = None


def get_planner(force_reload: bool = False) -> Planner:
    global _PLANNER
    if _PLANNER is not None and not force_reload:
        return _PLANNER
    settings = get_settings()
    if settings.llm_is_live:
        try:
            from medigraph.llm.openai_planner import OpenAIPlanner

            _PLANNER = OpenAIPlanner()
            return _PLANNER
        except Exception:  # pragma: no cover
            pass
    from medigraph.llm.mock_planner import MockPlanner

    _PLANNER = MockPlanner()
    return _PLANNER


def reset_planner() -> None:
    global _PLANNER
    _PLANNER = None


__all__ = ["get_planner", "reset_planner", "Planner"]
