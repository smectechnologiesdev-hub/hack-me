"""
Vaultline Heist — data-export decryptor (Stage 4).

The data export leaks two AES-256 secrets and two encrypted blobs:

    account_key + account_blob  ->  {username, password}
    vault_key   + vault_blob    ->  {vault_id, vault_password}

This recovers both.

No-script alternative: paste a blob as the text and its matching key as the
secret into the "aes256" tool at encode-decode.com (or open the bundled
tools/vaultline_decrypt.html).

Scheme (encode-decode.com compatible): key = secret zero-padded to 32 bytes,
IV = zeros, AES-256-CBC, PKCS#7, base64 output.

Usage:
    python tools/decrypt_vault.py vaultline_data_export.json
"""

import base64
import json
import sys

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def decrypt(blob: str, secret: str) -> dict:
    key = secret.encode()[:32].ljust(32, b"\x00")
    ct = base64.b64decode(blob)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(b"\x00" * 16)).decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return json.loads(unpadder.update(padded) + unpadder.finalize())


path = sys.argv[1] if len(sys.argv) > 1 else "vaultline_data_export.json"
data = json.load(open(path, encoding="utf-8"))

account = decrypt(data["account_blob"], data["account_key"])
vault = decrypt(data["vault_blob"], data["vault_key"])

print("[+] Decrypted account credentials:")
print("    Username       :", account["username"])
print("    Password       :", account["password"])
print("[+] Decrypted vault credentials:")
print("    Vault ID       :", vault["vault_id"])
print("    Vault password :", vault["vault_password"])
