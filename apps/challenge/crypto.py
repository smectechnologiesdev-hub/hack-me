"""
AES-256-CBC helpers for the Vaultline vault credentials — encode-decode.com
compatible scheme.

The data export encrypts two values — the account password and the vault
password — each under its own per-client **secret** (``account_key`` /
``vault_key``), which the export leaks alongside the ciphertext.  So the crypto
stage is: paste a value and its matching secret into an "AES-256 decrypt" site.

This deliberately matches the scheme used by encode-decode.com's "aes256" tool
(the site students actually reach for), so their ciphertext decrypts there:

    key = secret bytes, right-zero-padded (or truncated) to 32 bytes  (AES-256)
    iv  = 16 zero bytes
    AES-256-CBC, PKCS#7 padding, output = base64(ciphertext)   # no salt/header

NB: this is intentionally weak (zero IV, raw key, no salt → deterministic) — it
is a *training* target for the "recognise AES and decrypt it" stage, not a way
to protect real secrets.  It is byte-for-byte compatible with:

    * encode-decode.com  → paste ciphertext + secret, Decrypt
    * the bundled tools/vaultline_decrypt.html
    * PHP  openssl_decrypt(base64_decode($ct), 'aes-256-cbc', $secret, 0, str_repeat("\\0",16))
"""

import base64
import secrets

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_IV = b"\x00" * 16


def _key_bytes(secret: str) -> bytes:
    """secret -> 32-byte AES-256 key (right-zero-padded / truncated), PHP-style."""
    return secret.encode("utf-8")[:32].ljust(32, b"\x00")


def generate_key() -> str:
    """Return a fresh secret (<= 32 chars) for a client blob."""
    return secrets.token_hex(8)  # 16 hex chars — easy to copy into a website


def encrypt(plaintext: str, secret: str) -> str:
    """Encrypt a plain string as base64 AES-256-CBC (zero IV, PKCS#7).

    The plaintext is a raw value (e.g. a password), so decrypting on
    encode-decode.com returns exactly that value — no JSON wrapping to confuse
    a beginner.
    """
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    data = padder.update(plaintext.encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(_key_bytes(secret)), modes.CBC(_IV)).encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    return base64.b64encode(ct).decode()


def decrypt(blob: str, secret: str) -> str:
    """Reverse :func:`encrypt`.  Returns the plain string; raises on bad padding."""
    ct = base64.b64decode(blob)
    decryptor = Cipher(algorithms.AES(_key_bytes(secret)), modes.CBC(_IV)).decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode()
