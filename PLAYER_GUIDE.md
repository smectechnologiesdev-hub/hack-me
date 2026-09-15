# Vaultline Heist — Player Walkthrough

Play the challenge end to end, exactly as a student would. Everything here is
verified and runnable. You'll break into a Vaultline client's account, crack
open their vault, and capture the flag.

> **Your objective:** get in → find the leaked data → decrypt the vault
> credentials → open the vault → capture the flag `HM{...}`.

Run all commands from the project root:
`C:\Users\ANSON\Desktop\Projects\hack-me\hack-me`.
On PowerShell, `python` works as shown; the browser steps are the same everywhere.

---

## One-time setup

Open **two terminals**. In terminal A, set up and start the server:

```bash
pip install -r requirements.txt
python manage.py migrate

# Fresh set of targets, passwords drawn from the practice wordlist
python manage.py shell -c "from apps.challenge.models import VaultClient; VaultClient.objects.all().delete()"
python manage.py provision_challenge --count 8 --wordlist tools/wordlist.txt --min-rank 50 --max-rank 900 --assign

python manage.py runserver 127.0.0.1:8000
```

Leave that running. Use **terminal B** for the attack scripts below.

> During a real event you'd provision with `rockyou.txt` instead; here we use the
> bundled `tools/wordlist.txt` (4,000 passwords) so you can brute-force for real
> without downloading anything. Answers sit in the first ~900 lines so the run
> stays under the login rate-limit.

---

## Stage 0 — Get your target

1. Open **http://127.0.0.1:8000/register/** and create an account (this is
   *your* player account — not the victim).
2. You land on your **mission page** (`/dashboard/`). It shows **your target
   client's username** (e.g. `a.rutledge`), a progress tracker, and hints.

Note your target username — you'll use it below. (In this guide we'll use
`a.rutledge`; **substitute your own**.)

---

## Stage 1 — Break in (crack the login)

The client portal login is at **`/portal/login/`**. Two ways in:

### Option A — Brute-force (the main path)

In terminal B:

```bash
python tools/brute_force.py a.rutledge http://127.0.0.1:8000 tools/wordlist.txt
```

Expected — it finds the password in a few hundred tries:

```
[*] Brute-forcing a.rutledge at http://127.0.0.1:8000/portal/login/
[+] FOUND after 71 tries -> a.rutledge : gamer11
```

Write down the password it prints.

### Option B — SQL injection (no password needed)

Go to **http://127.0.0.1:8000/portal/login/** in a browser and enter:

| Field | Value |
|-------|-------|
| Client username | `a.rutledge' --` |
| Password | anything |

The trailing `' --` comments out the password check, so you're logged straight
in. (Try it — it's the classic auth-bypass.)

---

## Stage 2 — Log in and look around

Open **http://127.0.0.1:8000/portal/login/** in your browser and sign in with
your target's username + the cracked password (or use the SQLi trick above).

You're now in the victim's account. Notice:

- **Open Vault** panel = **🔒 Locked** — *"rotate your account password to enable
  vault access."*
- A **Profile** section.

You need the vault credentials — and they're not on screen. Head to Profile.

---

## Stage 3 — Find the leaked data

1. Click **Profile** (top nav).
2. In the **Data** section, click **Download my data**.
3. It saves **`vaultline_data_export.json`**.

Open it — it over-shares. It contains **two secrets** (`account_key`,
`vault_key`) and **two encrypted blobs** (`account_blob`, `vault_blob`). Classic
sensitive-data-exposure bug.

> Save the file into the project root (or note its path) for the next step.

---

## Stage 4 — Decrypt the credentials

Each blob is **AES-256 encrypted** (encode-decode.com compatible), unlocked
by its own key:

- `account_blob` + `account_key` → `{username, password}`
- `vault_blob` + `vault_key` → `{vault_id, vault_password}` ← what you need next

**In a browser (no script):** open an online **"aes256" decrypt** tool such as
[encode-decode.com](https://encode-decode.com/aes256-encrypt-online/) — paste a
blob into the text box and its **matching** key (`account_key` / `vault_key`)
into the **secret** box, then hit **Decrypt string**. (Or open the bundled
**`tools/vaultline_decrypt.html`**, which does the whole export at once.)

**With a script:**

```bash
python tools/decrypt_vault.py vaultline_data_export.json
```

Expected:

```
[+] Decrypted account credentials:
    Username       : w.kingsley
    Password       : piano69
[+] Decrypted vault credentials:
    Vault ID       : VLT-9761
    Vault password : ember-2127
```

(If your browser saved the file to Downloads, pass that path instead.)

---

## Stage 5 — Unlock the vault (rotate password)

The vault input stays locked until you rotate the account password.

1. In the portal, go to **Profile → Change password** (or the **Rotate password
   to unlock** button on the vault).
2. Set any new password (min 4 chars), confirm, submit.
3. The **Open Vault** panel flips to **Unlocked**.

---

## Stage 6 — Open the vault and grab the loot

1. Go to **Vault**.
2. Enter the **Vault ID** and **Vault password** you decrypted in Stage 4.
3. Click **Open vault** → then **Download** `vault_records.txt`.
4. Open the file — the last line is your flag:

```
FLAG: HM{18f16c2ef329098d}
```

---

## Stage 7 — Capture (submit the flag)

1. Go back to your **mission page** (`/dashboard/`).
2. Paste the flag into **Submit flag** → submit.
3. You'll see **"🎉 Flag accepted"** and jump to **1000 pts / 5 stages**.
4. Open the **Scoreboard** (`/scoreboard/`) — you're on the board. (Put it on a
   projector during the event; it auto-updates.)

🏁 **Challenge complete.**

---

## Speed-run (optional): the whole chain in one script

If you just want to confirm the whole thing works, `tools/solve.py` walks every
stage over HTTP using the SQLi path (so it needs only the username):

```bash
python tools/solve.py http://127.0.0.1:8000 a.rutledge
```

It prints the flag at the end. (You'd still submit it on the mission page as
your player account to score.)

---

## If you get stuck

- **Login script finds nothing?** You're using the wrong wordlist — pass
  `tools/wordlist.txt`, or check you typed the target username exactly.
- **Vault says locked even after decrypting?** You must *rotate your password*
  (Stage 5) — decrypting the creds isn't enough on its own.
- **Decrypt errors?** Make sure you're passing the downloaded
  `vaultline_data_export.json`, not editing it.
- **Rate-limited (429)?** You fired too many login requests in a minute; wait 60s.
- **Reset your run:** re-run the `provision_challenge` command from setup.

Every stage also has a hint on your mission page.
