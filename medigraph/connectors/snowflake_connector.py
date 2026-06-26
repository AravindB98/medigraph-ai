"""Snowflake warehouse connector (live, config).

Many health systems land EHR/claims data in a cloud warehouse (Snowflake,
BigQuery, Redshift) before graphing it — exactly the pattern the original
MediGraph prototype used. This connector reads MEDIGRAPH-style views from
Snowflake. The driver is imported lazily so the offline install stays slim.
"""
from __future__ import annotations

from typing import List, Optional

from medigraph.config import get_settings
from medigraph.connectors.base import (
    BaseConnector,
    ConnectorInfo,
    Direction,
    Standard,
    Status,
    register,
)
from medigraph.domain.models import PatientRecord


@register("snowflake")
class SnowflakeConnector(BaseConnector):
    info = ConnectorInfo(
        key="snowflake", name="Snowflake warehouse", standard=Standard.PROPRIETARY,
        direction=Direction.READ, status=Status.CONFIG,
        description="Reads MEDIGRAPH views from a Snowflake warehouse (needs credentials).",
        countries=["US", "IN"])

    def __init__(self, totp_code: Optional[str] = None):
        self.totp_code = totp_code
        self._settings = get_settings()

    def test_connection(self) -> str:
        if not self._settings.snowflake_configured:
            return "Snowflake not configured. Set SNOWFLAKE_* env vars to enable."
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_VERSION()")
            version = cur.fetchone()[0]
            return f"Connected to Snowflake (version {version})."
        finally:
            conn.close()

    def _connect(self):
        import snowflake.connector  # lazy

        s = self._settings
        params = dict(
            user=s.snowflake_user, account=s.snowflake_account,
            warehouse=s.snowflake_warehouse, database=s.snowflake_database,
            schema=s.snowflake_schema, role=s.snowflake_role)
        if s.snowflake_password:
            params["password"] = s.snowflake_password
        if self.totp_code:
            params["passcode"] = self.totp_code
        return snowflake.connector.connect(**params)

    def fetch_all(self, limit: Optional[int] = None) -> List[PatientRecord]:  # pragma: no cover
        raise NotImplementedError(
            "Map your Snowflake views to canonical records here. The bundled schema "
            "mirrors V_PATIENTS / V_CONDITIONS / V_MEDICATIONS / OBSERVATIONS.")
