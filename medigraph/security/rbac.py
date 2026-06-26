"""Role-based access control.

A compact RBAC model mapping clinical roles to permissions. Real hospital systems
gate every action on a permission; MediGraph mirrors that so the API and UI can
enforce least-privilege and so the audit trail records *who was allowed to do
what*.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class Permission(str, Enum):
    VIEW_PHI = "view_phi"                     # see identifiable patient data
    VIEW_DEIDENTIFIED = "view_deidentified"   # see de-identified data only
    RUN_DECISION_SUPPORT = "run_decision_support"
    BUILD_COHORT = "build_cohort"
    VIEW_ANALYTICS = "view_analytics"
    RUN_QUERY = "run_query"
    IMPORT_EXPORT = "import_export"           # FHIR/connector ingest & export
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT = "view_audit"


class Role(str, Enum):
    admin = "admin"
    clinician = "clinician"
    nurse = "nurse"
    analyst = "analyst"
    auditor = "auditor"


_ALL = set(Permission)

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.admin: set(_ALL),
    Role.clinician: {
        Permission.VIEW_PHI, Permission.RUN_DECISION_SUPPORT, Permission.BUILD_COHORT,
        Permission.VIEW_ANALYTICS, Permission.RUN_QUERY, Permission.IMPORT_EXPORT,
    },
    Role.nurse: {
        Permission.VIEW_PHI, Permission.RUN_DECISION_SUPPORT, Permission.VIEW_ANALYTICS,
        Permission.RUN_QUERY,
    },
    Role.analyst: {
        Permission.VIEW_DEIDENTIFIED, Permission.BUILD_COHORT, Permission.VIEW_ANALYTICS,
        Permission.RUN_QUERY,
    },
    Role.auditor: {
        Permission.VIEW_DEIDENTIFIED, Permission.VIEW_AUDIT,
    },
}


def permissions_for(role: Role) -> Set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in permissions_for(role)


def can_view_phi(role: Role) -> bool:
    return has_permission(role, Permission.VIEW_PHI)
