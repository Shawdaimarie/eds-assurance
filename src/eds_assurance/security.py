"""Static, scoped credentials for the reference service; replace with OIDC at scale."""

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


SCOPES = {"read", "write", "evaluate"}


@dataclass(frozen=True)
class Principal:
    tenant: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class Credential:
    token_digest: bytes
    principal: Principal


@dataclass(frozen=True)
class Settings:
    db_path: Path
    audit_key: bytes
    credentials: tuple[Credential, ...]
    max_body_bytes: int = 524_288

    @classmethod
    def from_env(cls):
        try:
            key = bytes.fromhex(os.environ["EDS_AUDIT_KEY_HEX"])
            raw = json.loads(os.environ["EDS_API_TOKENS_JSON"])
            if len(key) != 32 or not isinstance(raw, list) or not raw:
                raise ValueError
            credentials = []
            seen = set()
            for item in raw:
                if set(item) != {"token", "tenant", "scopes"}:
                    raise ValueError
                token, tenant, scopes = item["token"], item["tenant"], item["scopes"]
                if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_\-]{32,256}", token):
                    raise ValueError
                if not isinstance(tenant, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}", tenant):
                    raise ValueError
                if not isinstance(scopes, list) or not scopes or any(scope not in SCOPES for scope in scopes):
                    raise ValueError
                token_digest = hashlib.sha256(token.encode()).digest()
                if token_digest in seen:
                    raise ValueError
                seen.add(token_digest)
                credentials.append(Credential(token_digest, Principal(tenant, frozenset(scopes))))
            return cls(Path(os.environ.get("EDS_DB_PATH", ".local/assurance.db")), key, tuple(credentials))
        except (KeyError, ValueError, TypeError):
            raise ValueError("Invalid security configuration. Set a 32-byte EDS_AUDIT_KEY_HEX and valid EDS_API_TOKENS_JSON; see README.") from None

    def authenticate(self, token: str):
        candidate = hashlib.sha256(token.encode()).digest()
        principal = None
        for credential in self.credentials:
            if hmac.compare_digest(candidate, credential.token_digest):
                principal = credential.principal
        return principal
