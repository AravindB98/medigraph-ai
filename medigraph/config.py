"""Central configuration for MediGraph AI.

Settings are resolved from environment variables (optionally loaded from a local
`.env` file). The platform is designed to run with **no configuration at all** —
in that case it falls back to the bundled offline demo (embedded graph + synthetic
data + deterministic planner). Supplying credentials switches individual
subsystems to their live implementations.

Design goals:
- Zero-credential startup (great for demos, interviews and evaluation).
- Each subsystem (graph, LLM) can be live or offline *independently*.
- No secrets ever live in source control — only `.env` (gitignored) or real
  environment variables / secret managers in production.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:  # python-dotenv is optional; the app still runs without it.
    from dotenv import load_dotenv

    load_dotenv(override=False)
except Exception:  # pragma: no cover - dotenv is a convenience only
    pass


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PACKAGE_ROOT / "data" / "synthetic"
RUNTIME_DIR = Path(os.getenv("MEDIGRAPH_RUNTIME_DIR", PROJECT_ROOT / ".runtime"))


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings.

    Attributes mirror environment variables. Anything that is ``None`` means the
    corresponding live integration is disabled and the offline default is used.
    """

    # --- Branding -----------------------------------------------------------
    app_name: str = "MediGraph AI"
    app_tagline: str = "Clinical Knowledge Graph & Decision Support Platform"
    organization: str = os.getenv("MEDIGRAPH_ORG", "Demo Health System")

    # --- Graph backend ------------------------------------------------------
    # "embedded" (NetworkX over bundled synthetic data) or "neo4j" (live Aura).
    graph_backend: str = os.getenv("MEDIGRAPH_GRAPH_BACKEND", "embedded").lower()
    neo4j_uri: Optional[str] = os.getenv("NEO4J_URI")
    neo4j_user: Optional[str] = os.getenv("NEO4J_USER")
    neo4j_password: Optional[str] = os.getenv("NEO4J_PASSWORD")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # --- Snowflake (optional source-of-truth warehouse) ---------------------
    snowflake_account: Optional[str] = os.getenv("SNOWFLAKE_ACCOUNT")
    snowflake_user: Optional[str] = os.getenv("SNOWFLAKE_USER")
    snowflake_password: Optional[str] = os.getenv("SNOWFLAKE_PASSWORD")
    snowflake_warehouse: Optional[str] = os.getenv("SNOWFLAKE_WAREHOUSE")
    snowflake_database: Optional[str] = os.getenv("SNOWFLAKE_DATABASE")
    snowflake_schema: Optional[str] = os.getenv("SNOWFLAKE_SCHEMA")
    snowflake_role: Optional[str] = os.getenv("SNOWFLAKE_ROLE")

    # --- LLM ----------------------------------------------------------------
    # "mock" (deterministic offline planner) or "openai" (live).
    llm_provider: str = os.getenv("MEDIGRAPH_LLM_PROVIDER", "mock").lower()
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # --- Security -----------------------------------------------------------
    secret_key: str = os.getenv("MEDIGRAPH_SECRET_KEY", "dev-insecure-change-me")
    audit_log_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("MEDIGRAPH_AUDIT_LOG", RUNTIME_DIR / "audit.log.jsonl")
        )
    )
    token_ttl_minutes: int = int(os.getenv("MEDIGRAPH_TOKEN_TTL_MIN", "480"))

    # --- Synthetic data generation -----------------------------------------
    synthetic_patients: int = int(os.getenv("MEDIGRAPH_SYNTH_PATIENTS", "120"))
    synthetic_seed: int = int(os.getenv("MEDIGRAPH_SYNTH_SEED", "42"))

    # --- Derived helpers ----------------------------------------------------
    @property
    def graph_is_live(self) -> bool:
        return (
            self.graph_backend == "neo4j"
            and bool(self.neo4j_uri)
            and bool(self.neo4j_user)
            and bool(self.neo4j_password)
        )

    @property
    def llm_is_live(self) -> bool:
        return self.llm_provider == "openai" and bool(self.openai_api_key)

    @property
    def snowflake_configured(self) -> bool:
        return bool(self.snowflake_account and self.snowflake_user)

    @property
    def mode_summary(self) -> str:
        graph = "Neo4j (live)" if self.graph_is_live else "Embedded graph (offline)"
        llm = "OpenAI (live)" if self.llm_is_live else "Deterministic planner (offline)"
        return f"Graph: {graph} · LLM: {llm}"

    def ensure_runtime_dir(self) -> Path:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        return RUNTIME_DIR


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cached settings (used in tests after patching the environment)."""
    get_settings.cache_clear()
