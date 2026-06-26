"""Authentication: password hashing + JWT-style tokens (stdlib only).

Implemented with the standard library (PBKDF2-HMAC-SHA256 for passwords, a
spec-correct HS256 JWT for sessions) so the platform has real auth with **zero
extra dependencies**. In production you would point ``UserStore`` at your IdP /
LDAP / SMART-on-FHIR rather than the bundled demo users.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

from medigraph.config import get_settings
from medigraph.security.rbac import Role

# ---------------------------------------------------------------------------
# Password hashing (PBKDF2)
# ---------------------------------------------------------------------------
_PBKDF2_ROUNDS = 120_000


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Minimal HS256 JWT
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def encode_jwt(payload: dict, secret: Optional[str] = None, ttl_minutes: Optional[int] = None) -> str:
    settings = get_settings()
    secret = secret or settings.secret_key
    ttl = ttl_minutes if ttl_minutes is not None else settings.token_ttl_minutes
    header = {"alg": "HS256", "typ": "JWT"}
    body = dict(payload)
    now = int(time.time())
    body.setdefault("iat", now)
    body.setdefault("exp", now + ttl * 60)
    seg = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(body).encode())}"
    sig = hmac.new(secret.encode(), seg.encode(), hashlib.sha256).digest()
    return f"{seg}.{_b64url(sig)}"


def decode_jwt(token: str, secret: Optional[str] = None) -> dict:
    settings = get_settings()
    secret = secret or settings.secret_key
    try:
        header_b64, body_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("Malformed token") from exc
    seg = f"{header_b64}.{body_b64}"
    expected = hmac.new(secret.encode(), seg.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise ValueError("Invalid token signature")
    body = json.loads(_b64url_decode(body_b64))
    if body.get("exp", 0) < int(time.time()):
        raise ValueError("Token expired")
    return body


# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------
@dataclass
class User:
    username: str
    full_name: str
    role: Role
    password_hash: str


class UserStore:
    """In-memory user store seeded with demo users (offline-friendly)."""

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._seed_demo_users()

    def _seed_demo_users(self) -> None:
        demo = [
            ("dr.house", "Dr. Gregory House", Role.clinician, "clinician123"),
            ("nurse.joy", "Joy Nurse", Role.nurse, "nurse123"),
            ("analyst.sam", "Sam Analyst", Role.analyst, "analyst123"),
            ("admin", "System Administrator", Role.admin, "admin123"),
            ("auditor.lee", "Lee Auditor", Role.auditor, "auditor123"),
        ]
        for username, name, role, pwd in demo:
            self._users[username] = User(username, name, role, hash_password(pwd))

    def get(self, username: str) -> Optional[User]:
        return self._users.get(username)

    def add(self, username: str, full_name: str, role: Role, password: str) -> User:
        user = User(username, full_name, role, hash_password(password))
        self._users[username] = user
        return user

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self._users.get(username)
        if user and verify_password(password, user.password_hash):
            return user
        return None

    def list_users(self):
        return list(self._users.values())


_STORE: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _STORE
    if _STORE is None:
        _STORE = UserStore()
    return _STORE


def login(username: str, password: str) -> Optional[str]:
    """Authenticate and return a signed token, or None."""
    user = get_user_store().authenticate(username, password)
    if not user:
        return None
    return encode_jwt({"sub": user.username, "role": user.role.value, "name": user.full_name})
