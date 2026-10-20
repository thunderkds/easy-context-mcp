"""User accounts: password hashing and login checks."""

import hashlib
import hmac
import os

ITERATIONS = 200_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Derive a PBKDF2 hash for a new password."""
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return salt, digest


def verify_password(user: dict, password: str) -> bool:
    """Verify a user's password against the stored salt and hash."""
    _, digest = hash_password(password, user["salt"])
    return hmac.compare_digest(digest, user["password_hash"])
