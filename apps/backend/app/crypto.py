"""Fernet-based encryption for sensitive credentials (creds_encrypted).

Usage:
    from app.crypto import encrypt_creds, decrypt_creds

    encrypted = encrypt_creds({"password": "abc", "two_fa": "123456"})
    # → {"_enc": "gAAA...base64..."}

    plaintext = decrypt_creds(encrypted)
    # → {"password": "abc", "two_fa": "123456"}
"""

import json
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger("crypto")

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = settings.fernet_key
    if not key:
        logger.warning("FERNET_KEY not set — credentials will be stored in plaintext!")
        return None
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except Exception:
        logger.error("Invalid FERNET_KEY — cannot encrypt credentials")
        return None


def encrypt_creds(plaintext: dict | None) -> dict | None:
    """Encrypt a credentials dict into {"_enc": "<base64>"}.

    If FERNET_KEY is not configured, returns the dict as-is (backward compat).
    """
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    raw = json.dumps(plaintext, separators=(",", ":")).encode("utf-8")
    token = f.encrypt(raw)
    return {"_enc": token.decode("ascii")}


def decrypt_creds(stored: dict | None) -> dict | None:
    """Decrypt a {"_enc": "..."} dict back to plaintext.

    If the dict doesn't have "_enc", it's assumed to be plaintext (pre-migration data).
    """
    if not stored:
        return stored
    enc_value = stored.get("_enc")
    if not enc_value:
        # Pre-migration: stored in plaintext
        return stored
    f = _get_fernet()
    if f is None:
        logger.error("Cannot decrypt creds: FERNET_KEY not configured")
        return None
    try:
        raw = f.decrypt(enc_value.encode("ascii") if isinstance(enc_value, str) else enc_value)
        return json.loads(raw)
    except InvalidToken:
        logger.error("Cannot decrypt creds: invalid token (wrong key?)")
        return None
    except Exception as e:
        logger.error("Cannot decrypt creds: %s", e)
        return None
