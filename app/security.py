import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone

HTML_TAG_RE = re.compile(r"<[^>]+>")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_text(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip()
    cleaned = CONTROL_RE.sub(" ", cleaned)
    cleaned = HTML_TAG_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def sanitize_list(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        item = sanitize_text(value)
        if item and item not in result:
            result.append(item)
    return result


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
