"""
Vaultline Heist — data-export decryptor (Stage 4).

The data export gives the username and vault id in the clear, and leaks two
AES-256 secrets with two encrypted values:

    algorithm_key        + encrypted_password        ->  account password
    vault_algorithm_key  + encrypted_vault_password  ->  vault password

This recovers both passwords.

No-script alternative: paste an encrypted value as the text and its matching key
as the secret into the "aes256" tool at encode-decode.com (or open the bundled
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


def decrypt(blob: str, secret: str) -> str:
    key = secret.encode()[:32].ljust(32, b"\x00")
    ct = base64.b64decode(blob)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(b"\x00" * 16)).decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode()


path = sys.argv[1] if len(sys.argv) > 1 else "vaultline_data_export.json"
data = json.load(open(path, encoding="utf-8"))

password = decrypt(data["encrypted_password"], data["algorithm_key"])
vault_password = decrypt(data["encrypted_vault_password"], data["vault_algorithm_key"])

print("[+] Account credentials:")
print("    Username       :", data["username"])
print("    Password       :", password)
print("[+] Vault credentials:")
print("    Vault ID       :", data["vault_id"])
print("    Vault password :", vault_password)
