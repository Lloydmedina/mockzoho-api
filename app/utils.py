import random
from datetime import datetime, timedelta, timezone

from app.config import settings

MOCK_USER = {"id": "4876000000123001", "name": "Mock Integration User"}


def _tzinfo() -> timezone:
    offset = settings.timezone_offset.strip()
    sign = -1 if offset.startswith("-") else 1
    body = offset.lstrip("+-")
    hours, _, minutes = body.partition(":")
    return timezone(sign * timedelta(hours=int(hours or 0), minutes=int(minutes or 0)))


def now_iso() -> str:
    """ISO 8601 timestamp with offset, matching Zoho's format."""
    return datetime.now(_tzinfo()).isoformat(timespec="seconds")


def new_record_id() -> str:
    """19-digit numeric string, shaped like a real Zoho record id."""
    return f"4876{random.randint(10**14, 10**15 - 1)}"


def new_access_token() -> str:
    return f"1000.{random.randbytes(16).hex()}.{random.randbytes(16).hex()}"


def audit_stamp() -> dict[str, str]:
    return dict(MOCK_USER)
