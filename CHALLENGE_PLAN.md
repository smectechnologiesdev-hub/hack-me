# Vaultline Heist — CTF Challenge Plan

> A staged, story-driven breach challenge built on the existing "Vaultline"
> private-banking app. Players break into a client's account, uncover an
> over-sharing data export, decrypt the vault credentials, and exfiltrate the
> loot.

**North-star constraint:** a student with **zero background** must be able to
make progress using **AI + the internet**, while students who know some
security still have real depth to chew on. Every stage has a clear, discoverable
next step (realistic UI signposts) even when the *work* is non-trivial.

---

## 1. The kill chain (core flow)

| # | Stage | Player action | Skill taught | Difficulty |
|---|-------|---------------|--------------|------------|
| 1 | **Break in** | Brute-force the password **or** SQL-injection auth bypass on the login | Broken auth, wordlists, SQLi | ★–★★ |
| 2 | **Recon dashboard** | Explore the account; find the locked **Open Vault** panel + banking sections | Enumeration, reading an app | ★ |
| 3 | **Data export leak** | Profile → **Data** → **Download my data** → a JSON export that over-shares | Sensitive data exposure | ★★ |
| 4 | **Decrypt vault creds** | Use the leaked `key` to **decrypt** the vault id + vault password | Crypto handling / reversing | ★★–★★★ |
| 5 | **Rotate password** | Reset the account password to **unlock** the vault input (server-side gate) | Auth/logic flow | ★★ |
| 6 | **Open vault & exfiltrate** | Enter vault id + password → **download the loot files** = final flag | Exfiltration | ★★ |

The path is **linear and forced**: you can't open the vault without the
decrypted creds (stage 4) *and* a rotated password (stage 5), and you can't get
the creds without the data export (stage 3), which you only find while looking
for the password reset.

---

## 2. Narrative

Vaultline is a private bank. You've been hired to breach client **`<target>`**,
get past their account security, and empty their vault. Each stage is a flag;
the loot files in the vault carry the final flag.

Flag format: `HM{...}` (configurable).

---

## 3. Stage details

### Stage 1 — Break in

Two entry paths into the **same** target account (player picks one):

- **Brute-force** — the account password is drawn from the real `rockyou.txt`
  at **moderate depth** (a few hundred to a couple thousand lines in — never the
  top 20). This is the key anti-"trivial-loop" move: it is *not* a handed-out
  9-word list, but it **is** in rockyou, which is the wordlist every AI tells a
  beginner to download. So a zero-background student following AI guidance cracks
  it in minutes; a strong student just does it faster.
  - Beginner/AI path: *"how do I brute-force the login at `http://SERVER/login/`
    for user X in Python"* → works against the JSON `{username,password}` endpoint.
- **SQL injection** — a deliberately vulnerable login that builds SQL by string
  interpolation, so `' OR '1'='1' -- ` bypasses authentication and logs you into
  the target account.
  - Beginner/AI path: SQLi auth-bypass is one of the most-documented attacks on
    the internet; AI walks them straight through it.

**Decision — what SQLi yields** (see §11): recommended = **auth-bypass only**
(lands on the same locked dashboard as the brute-force crowd, so everyone
converges on the chain). The vault creds live in a table the injectable query
**cannot** reach, so injection gets you *in* but doesn't skip the puzzle.

**Implementation note:** Django stores passwords hashed, so the injectable login
uses a separate, isolated **`VaultClient`** table (`username`, `password`) queried
with raw string-built SQL. The real Django admin/auth stays safe; the vuln is
contained to the challenge login.

### Stage 2 — Recon the dashboard

After login the player sees a themed banking interface:

- **Open Vault** panel — visibly **locked**: *"🔒 Rotate your account password to
  enable vault access."* Shows disabled `vault_id` + `vault_password` inputs.
- **Profile** section (typical items: name, email, security, **Data**).
- **Accounts / Statements** section (bank-themed; optional home for a bonus IDOR
  flag — see §10).

The locked vault is the signpost that drives the player toward the password
reset, which lives in Profile.

### Stage 3 — Data export leak

In **Profile → Data**, a realistic GDPR-style **"Download my data"** button
returns a JSON export that **over-shares** (a real, common bug class). Example:

```json
{
  "display_name": "M Kessler",
  "account_key": "the AES-256 secret for the account blob",
  "account_blob": "base64( AES-256-CBC ciphertext )",
  "vault_key": "the AES-256 secret for the vault blob",
  "vault_blob": "base64( AES-256-CBC ciphertext )"
}
```

Each blob decrypts to a small JSON, under its **own** key:

- `account_blob` + `account_key` → `{username, password}`.
- `vault_blob` + `vault_key` → `{vault_id, vault_password}` (the Stage-6 objective).

Both ciphertext blobs are generated fresh at export time; only the two secrets
are stored. Encrypting the account creds is a **bonus** decrypt (the export is
post-login, so it's not chain-critical) — it keeps the crypto stage symmetrical
and gives two reps of the same skill.

### Stage 4 — Decrypt the credentials

Both id/password pairs are **encrypted (reversible), not hashed** — a hash could
never be turned back into a vault id. Scheme: **AES-256-CBC, matching the
encode-decode.com "aes256" tool** so the ciphertext decrypts there directly.

- The recognition cue: a **secret** (`account_key` / `vault_key`) + a base64
  **ciphertext** (`…_blob`) → AES-256, "paste a secret" style.
- **Chosen for accessibility:** it takes a single **secret**, not a raw key + IV.
  A student who can't write a script pastes a blob + its matching key into
  encode-decode.com (or the bundled `tools/vaultline_decrypt.html`) and gets the
  JSON. This works because we match that site's exact (weak) convention below.
- Format details (deliberately weak — a *training* target, not real protection):
  `key = secret bytes right-zero-padded/truncated to 32`, `IV = 16 zero bytes`,
  AES-256-CBC, PKCS#7, `output = base64(ciphertext)` (no salt, no header).
  Equivalent to `openssl_decrypt(base64_decode($ct), 'aes-256-cbc', $secret, 0,
  str_repeat("\0", 16))`.

```python
# scripted equivalent — see apps/challenge/crypto.py / tools/decrypt_vault.py
import base64, json
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

key = vault_key.encode()[:32].ljust(32, b"\0")   # secret zero-padded to 32 bytes
ct  = base64.b64decode(vault_blob)
dec = Cipher(algorithms.AES(key), modes.CBC(b"\0" * 16)).decryptor()
data = json.loads(padding.PKCS7(128).unpadder().update(
    dec.update(ct) + dec.finalize()))
```

Beginner-safe (paste into a website, no fields to fiddle with), still a genuine
"recognize the format and reverse the crypto" moment. Trade-off: zero IV + raw
key + no salt is intentionally weak (deterministic) — fine for a training CTF,
never for real secrets.

### Stage 5 — Rotate the account password

The **Open Vault** input is gated **server-side** on a real password rotation
(`password_rotated = True`), not just a disabled field in the browser — otherwise
a strong student calls the vault endpoint directly and skips it. The password
reset lives in Profile; rotating it flips the gate and (per the §3 option)
releases the export secrets (`account_key` / `vault_key`).

### Stage 6 — Open the vault & exfiltrate

With the vault unlocked (stage 5) and the decrypted creds (stage 4), the player
enters `vault_id` + `vault_password` → the vault opens → they **download the loot
files**. The files (e.g. a "stolen documents" bundle, an image, a text file)
contain the **final flag** `HM{...}`.

---

## 4. Data & crypto spec

| Item | Storage | Purpose |
|------|---------|---------|
| Account password | Django hash (normal auth) + rockyou-depth plaintext behind the scenes for the target | Stage 1 brute-force |
| `VaultClient.password` | Isolated table, raw-SQL login only | Stage 1 SQLi auth-bypass |
| `account_key` / `account_blob` | Account `username` + `password` **AES-256 encrypted** in the export | Stage 4 (bonus decrypt) |
| `vault_key` | AES-256 secret for the vault blob, leaked in export | Stage 4 decryption key |
| `vault_blob` | `vault_id` + `vault_password` **AES-256 encrypted** (secret = `vault_key`) in the export | Stage 4 → Stage 6 |
| `password_rotated` | Boolean on the target | Stage 5 server-side gate |
| Vault loot files | Files served only after vault open | Stage 6 final flag |

---

## 5. Per-student instancing

To keep the scoreboard honest (a shared decrypted vault password would leak to
the whole room), each player gets their **own** instanced target: own login
creds, own `account_key`/`vault_key`, own vault files, own final flag — all **generated** by
a management command, not hand-made:

```
python manage.py provision_challenge --count 30
```

Each student is assigned one target on registration (shown on their dashboard).
Cracking someone else's target earns nothing, because a flag only credits the
student it was issued to.

> Alternative (less build, weaker anti-cheat): one shared Vaultline instance and
> the scoreboard tracks per-student **stage progress** instead of secret flags.

---

## 6. Scoring & live scoreboard

- Per-stage flags with escalating points, e.g.
  **S1 100 · S3 150 · S4 250 · S6 400** (+ a **first-blood bonus** on the hard
  stages).
- Public **`/scoreboard/`** with live updates (reuses the existing Django
  Channels / WebSocket stack).
- Flag submission credits only the assigned student and timestamps the solve, so
  the board ranks by progress **and** speed.
- Instructor view: existing attempts/monitor log + the scoreboard.

---

## 7. Hints (safety net for the zero-background crowd)

Tiered, small point cost, one set per stage — so nobody hard-stalls on "where do
I go next." Discoverability comes from realistic UI (the 🔒 vault label, the
"Download my data" button); the hints cover the *technique* (e.g. "a 32-byte key
+ a ciphertext means AES-256 — paste into a website with the secret").

---

## 8. What it teaches (why it's strong)

Broken authentication (brute-force / SQLi) → **sensitive data exposure** (the
over-sharing export) → **weak crypto handling** (creds encrypted with a leaked
key) → **forced-rotation logic flaw** → **exfiltration**. Four separate
OWASP-flavored lessons inside one story, with a difficulty curve that serves both
skill levels.

---

## 9. Optional / stretch flags (so strong students don't finish and idle)

Nearly-free add-ons using sections we're already building:

- **IDOR** on the Statements section: `/account/<id>/statement/` → change the id
  → another client's data + a flag.
- **The heist capstone:** a money-transfer endpoint with no lock / no
  balance-check → race-condition double-spend to drain the vault account.
- **Rate-limit bypass:** rotate `X-Forwarded-For` to evade the per-IP login
  throttle (the code already trusts that header when computing client IP).

---

## 10. Build plan (Django, file-level)

**New / changed:**

- `apps/labs` (or a new `apps/challenge`):
  - `VaultClient` model (isolated, SQLi-vulnerable login table).
  - `TargetProfile` model: assigned player, `account_key`/`vault_key`, `vault_id_enc`,
    `vault_password_enc`, `password_rotated`, `flag`, loot file refs.
  - `provision_challenge --count N` management command (rockyou-sourced
    passwords, AES-256 keys, per-target flags + loot).
- `apps/accounts/views.py`:
  - Injectable raw-SQL challenge login (contained vuln).
  - Add the login throttle (currently none on `/login/`).
- Dashboard templates:
  - Locked **Open Vault** panel (server-side gated).
  - **Profile → Data → Download my data** export view (JSON).
  - Vault open + loot download view.
- Scoreboard app: `/scoreboard/`, flag-submit, live WebSocket updates.
- `requirements.txt`: add `cryptography` (provides AES-256-CBC via `Cipher`).

**Reuses as-is:** Channels/WebSocket live updates, attempts logging, instructor
dashboard, the `/login/` JSON contract, `select_for_update` locking pattern
(as the *secure* counter-example to the deliberately-unlocked heist endpoint).

---

## 11. Decisions (resolved)

1. **SQLi scope** — ✅ **auth-bypass only**. The portal login is an auth-bypass
   oracle that reflects no row data, so UNION-dumping is out of scope.
2. **Instancing** — ✅ **per-student generated targets** (`provision_challenge`);
   flags are bound to the assigned student, so the scoreboard stays honest.
3. **Optional flags** (§9) — not built yet; the core chain ships first.
4. **Logistics** — class size + time budget still to confirm (tunes rockyou
   depth via `--min-rank/--max-rank`, the throttle ceiling, and points).
5. **Student tooling** — Python starter shipped on the mission page; a `hydra`
   one-liner for Kali users is a nice-to-add.

---

## 12. Implementation status (built)

A self-contained `apps/challenge` app implements the full core chain. **50/50
tests pass**; the whole chain is verified end to end (crack → data export →
AES-256 decrypt → gated rotation → vault open → flag → scoreboard).

- `VaultClient` model = one per-student target (login creds, AES-256 vault blob,
  flag, milestone timestamps).
- Vulnerable portal login (`/portal/login/`) — brute-force **and** SQLi
  auth-bypass, per-IP throttled.
- The chain: victim dashboard, Profile → **Download my data** (JSON leak),
  password rotation (server-side vault gate), vault open, loot download.
- `/scoreboard/` live board (polling) + flag submission bound to the assigned
  student.
- Mission page at `/dashboard/` (target, starter script, tiered hints, progress,
  submit).
- Auto-assign a target on registration; `provision_challenge --count N` command.

### How to run

```bash
pip install -r requirements.txt          # adds `cryptography`
python manage.py migrate
# Provision targets (point at the SAME rockyou students will use):
python manage.py provision_challenge --count 30 \
    --wordlist /path/to/rockyou.txt --assign
python manage.py runserver
```

Students: register at `/register/` → mission at `/dashboard/` → attack
`/portal/login/`. Watch `/scoreboard/`.

### Still to tune / optional

- Pass a real `rockyou.txt` to `provision_challenge` so every target password is
  guaranteed crackable from the list students use.
- For a class > ~15: deploy on **Postgres + Redis**, and point Django's cache at
  Redis so the login throttle is shared across workers.
- Optional depth flags (§9): IDOR, the money-transfer heist, XFF throttle bypass.
- The legacy `/login/` + startup `abraham` seed still exist — leave or remove.

---

## 12. Event-day runbook (draft)

1. Deploy with **Postgres + Redis** (recommended for a class > ~15 — safer under
   all the concurrent attempt-writes than SQLite).
2. `python manage.py provision_challenge --count <students>`.
3. Confirm the login throttle and scoreboard are live.
4. Hand each student their target username + the starter script + scoreboard URL.
5. Watch `/scoreboard/` + the attempts monitor during the event.
6. Debrief: show the secure vs insecure code (locking, crypto, data export) side
   by side.

---

*Generated as the working plan for the Vaultline Heist challenge. Update the
Open Decisions section as they're resolved, then implementation can begin.*
