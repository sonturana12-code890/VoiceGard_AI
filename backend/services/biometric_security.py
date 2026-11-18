"""
VOICEGUARD AI — Biometric Voiceprint Security & Encryption Service
Cryptographic routines for encrypting, decrypting, and sanitizing 192-dimensional
ECAPA-TDNN latent speaker embeddings in the database.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.

Security Mandates:
- Never expose raw floating-point embeddings in API responses or plaintext storage.
- Encrypt latent representations using authenticated keystream cipher with random salt and HMAC-SHA256 tag.
- Protect cross-user biometric profile isolation.
- Discard raw audio recordings after embedding extraction.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from typing import Optional

import numpy as np

from backend.auth import SECRET_KEY

EMBEDDING_DIM = 192
_SPEAKER_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]{3,64}$")


def generate_speaker_id(prefix: str = "SPK") -> str:
    """Generates a unique, human-readable biometric speaker ID."""
    token = secrets.token_hex(4).upper()
    return f"{prefix}-{token}"


def validate_speaker_id(speaker_id: str) -> bool:
    """Validates that a speaker ID contains only safe alphanumeric and hyphen/underscore characters."""
    if not speaker_id or not isinstance(speaker_id, str):
        return False
    return bool(_SPEAKER_ID_REGEX.match(speaker_id.strip()))


def _derive_biometric_key(salt: bytes) -> bytes:
    """Derives a 256-bit AES-grade symmetric key from the application secret key using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac("sha256", SECRET_KEY.encode("utf-8"), salt, 10000, dklen=32)


def encrypt_embedding(embedding: np.ndarray) -> str:
    """
    Encrypts a 192-dimensional float32 embedding into an authenticated base64 string.
    Generates a cryptographically random 16-byte salt per encryption, builds an HMAC counter
    keystream, encrypts the raw vector bytes, and prepends an HMAC-SHA256 authentication tag.
    """
    arr = np.asarray(embedding, dtype=np.float32)
    if arr.ndim > 1:
        arr = arr.flatten()
    if arr.shape[0] != EMBEDDING_DIM:
        raise ValueError(f"Expected {EMBEDDING_DIM}-dimensional embedding, got {arr.shape[0]}.")

    salt = secrets.token_bytes(16)
    key = _derive_biometric_key(salt)
    raw_bytes = arr.tobytes()

    # Counter-mode keystream generation via HMAC-SHA256
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(raw_bytes):
        block = hmac.new(key, counter.to_bytes(4, "big"), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1

    ciphertext = bytes(b ^ k for b, k in zip(raw_bytes, keystream[:len(raw_bytes)]))
    tag = hmac.new(key, salt + ciphertext, hashlib.sha256).digest()
    payload = salt + tag + ciphertext
    return base64.b64encode(payload).decode("utf-8")


def decrypt_embedding(token: str) -> np.ndarray:
    """
    Decrypts an authenticated base64 string back into the exact 192-dimensional float32 embedding.
    Verifies the HMAC-SHA256 signature before decryption to detect tampering.
    """
    if not token or not isinstance(token, str):
        raise ValueError("Invalid embedding token.")

    try:
        payload = base64.b64decode(token.encode("utf-8"))
    except Exception as exc:
        raise ValueError("Malformed base64 embedding payload.") from exc

    if len(payload) < 48:
        raise ValueError("Embedding payload too short.")

    salt = payload[:16]
    tag = payload[16:48]
    ciphertext = payload[48:]

    key = _derive_biometric_key(salt)
    expected_tag = hmac.new(key, salt + ciphertext, hashlib.sha256).digest()

    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Biometric embedding integrity verification failed (tampered ciphertext).")

    keystream = bytearray()
    counter = 0
    while len(keystream) < len(ciphertext):
        block = hmac.new(key, counter.to_bytes(4, "big"), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1

    raw_bytes = bytes(c ^ k for c, k in zip(ciphertext, keystream[:len(ciphertext)]))
    embedding = np.frombuffer(raw_bytes, dtype=np.float32)

    if embedding.shape[0] != EMBEDDING_DIM:
        raise ValueError(f"Decrypted vector length {embedding.shape[0]} != {EMBEDDING_DIM}.")

    return embedding
