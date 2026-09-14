"""In-memory access token store with real TTL expiry."""

import time
from dataclasses import dataclass, field

from app.config import settings
from app.utils import new_access_token


@dataclass
class IssuedToken:
    access_token: str
    expires_at: float
    scope: str

    @property
    def expires_in(self) -> int:
        return max(0, int(self.expires_at - time.time()))

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


@dataclass
class TokenStore:
    tokens: dict[str, IssuedToken] = field(default_factory=dict)
    issued_count: int = 0

    def issue(self, scope: str, ttl: int | None = None) -> IssuedToken:
        ttl = settings.token_ttl_seconds if ttl is None else ttl
        token = IssuedToken(
            access_token=new_access_token(),
            expires_at=time.time() + ttl,
            scope=scope,
        )
        self.tokens[token.access_token] = token
        self.issued_count += 1
        return token

    def get(self, access_token: str) -> IssuedToken | None:
        return self.tokens.get(access_token)

    def is_valid(self, access_token: str) -> bool:
        token = self.tokens.get(access_token)
        return token is not None and not token.expired

    def revoke(self, access_token: str) -> bool:
        return self.tokens.pop(access_token, None) is not None

    def expire_all(self) -> int:
        now = time.time()
        count = 0
        for token in self.tokens.values():
            if not token.expired:
                token.expires_at = now
                count += 1
        return count

    def clear(self) -> None:
        self.tokens.clear()
        self.issued_count = 0


token_store = TokenStore()
