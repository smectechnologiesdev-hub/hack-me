# Brute-Force Authentication Training Lab

A Django web application for teaching students **how HTTP authentication
requests and password-guessing work**, in a fully controlled, isolated training
environment.

Each student gets their own **isolated lab** with a unique, unguessable token, a
training username, and a server-controlled wordlist. They write a small Python
`requests` script that POSTs candidate passwords to **their own** lab endpoint,
watch every attempt stream into a **live dashboard** over WebSockets, and stop
when authentication succeeds.

> ⚠️ **Authorized training environment only.** This platform is intentionally
> designed for educational security exercises against its own training
> endpoints. It is **not** a generic attack tool: it never accepts a target
> URL and can never fetch, proxy, forward, or attack any external system.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Features](#2-features)
3. [Architecture](#3-architecture)
4. [Installation](#4-installation)
5. [Environment setup](#5-environment-setup)
6. [Database setup](#6-database-setup)
7. [Redis setup](#7-redis-setup)
8. [Running Django](#8-running-django-development)
9. [Running ASGI](#9-running-asgi-websockets)
10. [Creating an admin user](#10-creating-an-admin-user)
11. [Creating wordlists](#11-creating-wordlists)
12. [Student workflow](#12-student-workflow)
13. [Instructor workflow](#13-instructor-workflow)
14. [AWS Lightsail deployment](#14-aws-lightsail-deployment)
15. [Security design decisions](#15-security-design-decisions)
16. [API documentation](#16-api-documentation)

---

## 1. Project overview

Students learn how Python's `requests` module talks to a web server by
performing a brute-force password exercise against a **simulated vulnerable
authentication endpoint** that belongs only to them. The simulation
deliberately omits password rate-limiting (guessing is the whole point) while
**infrastructure-level protections stay fully enabled** (throttling, request
size limits, CSRF on forms, secure production settings, lab attempt caps, and
lab expiry).

## 2. Features

- **Accounts & roles** — self-service student registration; instructor accounts
  (staff) for oversight. Custom `User` model with a `role` field.
- **Isolated labs** — one lab per student, addressed by a cryptographically
  random `lab_token`. The correct password is chosen server-side and stored
  **only as a Django password hash** — never exposed anywhere.
- **Server-controlled wordlists** — predefined datasets (Easy/Medium/Hard).
  Students cannot upload or create their own.
- **Training auth endpoint** — `POST /api/labs/<token>/login/`; logs every
  attempt, completes the lab on success, enforces expiry and attempt caps.
- **Concurrency-safe** — `select_for_update` row locks + atomic transactions so
  a multi-threaded script can never bypass `max_attempts`.
- **Live monitoring** — Django Channels + WebSockets push each attempt to the
  student's own dashboard in real time. Events never cross labs.
- **Instructor dashboard** — students, active/completed labs, total attempts,
  success rate, and filterable activity logs; plus Django admin actions
  (disable / reset labs).
- **Interactive learning pages** — request-flow explanation, per-lab exercise
  page with a constrained (non-generic) Python template and copy buttons.
- **Production-ready** — split settings, `.env` secrets, secure headers,
  WhiteNoise static, Docker, Nginx + systemd, Let's Encrypt guidance.

## 3. Architecture

```
Internet
    │
    ▼
  Nginx  (TLS termination, static/media, WebSocket upgrade)
    │
    ▼
Django ASGI application (Daphne)
    ├── Django (HTTP: pages + REST API)
    └── Django Channels (WebSocket: live monitor)
            │
            ▼
          Redis  (Channels layer — shares events across workers)

PostgreSQL (labs, attempts, users)
```

**Django apps** (`apps/`):

| App        | Responsibility                                              |
|------------|-------------------------------------------------------------|
| `core`     | Public home page, health check, shared context processors   |
| `accounts` | Custom `User` model, registration/login/logout              |
| `labs`     | `Wordlist` + `Lab` models, lab lifecycle service, REST API, HTML pages |
| `attempts` | `Attempt` model, concurrency-safe login service, WebSocket consumer/routing |
| `dashboard`| Student dashboard + instructor dashboard views              |

Business logic lives in **service layers** (`apps/labs/services.py`,
`apps/attempts/services.py`), keeping views and serializers thin.

## 4. Installation

**Requirements:** Python 3.12–3.14 (validated on 3.14 with Django 6.0). For
Python 3.11, pin Django to 5.2 LTS in `requirements.txt` — the code supports
both.

```bash
git clone <your-repo-url> bruteforce-lab
cd bruteforce-lab

python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## 5. Environment setup

```bash
cp .env.example .env
# Generate a strong secret key:
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# Paste it into SECRET_KEY in .env
```

Key variables (see `.env.example` for the full list):

| Variable                        | Purpose                                        |
|---------------------------------|------------------------------------------------|
| `SECRET_KEY`                    | Django secret (required)                        |
| `DEBUG`                         | `True` locally, **`False`** in production       |
| `ALLOWED_HOSTS`                 | Comma-separated hostnames                       |
| `CSRF_TRUSTED_ORIGINS`          | Comma-separated origins (scheme required)       |
| `DJANGO_SETTINGS_MODULE`        | `config.settings.dev` or `config.settings.prod` |
| `DATABASE_URL`                  | Blank = SQLite; else a Postgres URL             |
| `REDIS_URL`                     | Blank = in-memory Channels (dev only)           |
| `LAB_MAX_ATTEMPTS`              | Default attempt cap per lab (100)               |
| `LAB_DURATION_MINUTES`          | Default lab lifetime (60)                       |
| `SHOW_FULL_CANDIDATE_PASSWORDS` | Show full (vs masked) candidates in own lab     |

## 6. Database setup

**Local (SQLite, zero config)** — leave `DATABASE_URL` blank:

```bash
python manage.py migrate
```

**PostgreSQL** — install the driver and set `DATABASE_URL`:

```bash
pip install "psycopg[binary]"
# .env:
# DATABASE_URL=postgres://lab_user:lab_password@127.0.0.1:5432/lab_db
python manage.py migrate
```

The SQLite config uses WAL journaling + `BEGIN IMMEDIATE` transactions and a
busy-timeout so the concurrency-safe attempt processing behaves correctly even
on SQLite. **PostgreSQL is recommended for production** (true row-level locks).

## 7. Redis setup

Redis backs the Channels layer so WebSocket events are shared across worker
processes. In development you can skip it entirely — with `REDIS_URL` blank the
project uses an in-memory layer (single process only).

```bash
# Local Redis (Docker):
docker run -p 6379:6379 redis:7-alpine
# .env:
# REDIS_URL=redis://127.0.0.1:6379/0
```

In production settings (`config.settings.prod`), `REDIS_URL` is **required**.

## 8. Running Django (development)

```bash
python manage.py seed_wordlists     # create the predefined wordlists
python manage.py runserver
# http://127.0.0.1:8000
```

`runserver` uses Daphne (the `daphne` app is installed), so WebSockets work in
development out of the box with the in-memory channel layer.

## 9. Running ASGI (WebSockets)

To run the ASGI server explicitly (as in production):

```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

The WebSocket endpoint is `ws://<host>/ws/labs/<lab_token>/`. Connections are
authenticated via the Django session and authorized against lab ownership.

## 10. Creating an admin user

```bash
python manage.py createsuperuser
```

A superuser can log into `/admin/`. To make a normal account an instructor with
access to the custom instructor dashboard, set its **role = Instructor** and
**is_staff = True** in the admin (both are required — see security notes).

Create an instructor non-interactively:

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model as g; \
U=g(); U.objects.create_superuser('prof','prof@example.com','ChangeMe123!', role='INSTRUCTOR')"
```

## 11. Creating wordlists

The predefined datasets are created by a management command (idempotent):

```bash
python manage.py seed_wordlists
```

Instructors can also add/edit wordlists in Django admin (name, description,
difficulty, and a JSON list of passwords, e.g. `["password", "123456", ...]`).
Students can never create or upload wordlists.

**Setting a specific target account.** To hand-pick the target username and
password a student must brute-force (instead of a random one), use:

```bash
python manage.py create_lab <student_username> --username admin --password hello123
```

If the chosen password isn't already in the assigned wordlist it's added
automatically, so students can find it. The command prints the lab token and
endpoint (and the target password, for your reference only).

## 12. Student workflow

1. **Register / log in** at `/register/` or `/login/`.
2. Open **Labs** → **Start new lab** (optionally choose a difficulty).
3. On the lab page, copy your **endpoint URL**, **username**, and view your
   **wordlist** on the instructions page.
4. Write a Python `requests` loop (a per-lab template is provided) that POSTs
   `{"username": ..., "password": candidate}` to your endpoint.
5. Run it; read `response.json()["success"]`; `break` on success.
6. Watch attempts appear live on **Monitor**.

On the exercise page, click **Download passwords.txt** to save your wordlist,
then run a standalone script that reads it line by line. **No platform login is
needed inside the script** — your unguessable lab token in the URL is the
credential.

**Minimal working script** (`USERNAME` and `LAB_URL` are pre-filled on your
exercise page; save it next to `passwords.txt`):

```python
import requests

LAB_URL  = "http://127.0.0.1:8000/api/labs/YOUR_TOKEN/login/"
USERNAME = "student_xxxxxxxx"          # the target account username

with open("passwords.txt") as f:
    for line in f:
        password = line.strip()        # remove the trailing newline
        if not password:
            continue
        r = requests.post(LAB_URL, json={"username": USERNAME, "password": password})
        print(password, r.status_code)
        if r.json()["success"]:
            print("FOUND:", password)
            break
```

> **How it's authorized.** The lab token is a secret capability shown only to
> the lab's owner (and staff). Possessing it authorizes attempts against that
> lab, so the standalone script needs no session or CSRF token. Every attempt is
> still logged (IP + user-agent) and infrastructure throttling still applies.

## 13. Instructor workflow

- **`/instructor/`** — overview tiles (total students, active/completed labs,
  total attempts, success rate) and a recent-activity feed.
- **`/instructor/labs/`** — every lab, filterable by status and student.
- **`/instructor/attempts/`** — global attempt log, filterable by result,
  student, and lab token.
- **`/admin/`** — full model access, plus lab actions: **Disable**, **Enable**,
  and **Reset** (wipes attempts and re-arms with a fresh target).

## 14. AWS Lightsail deployment

Target: **Ubuntu** Lightsail instance, **Nginx → Daphne (ASGI) → Django +
Channels**, **PostgreSQL**, **Redis**, TLS via **Let's Encrypt**.

```bash
# 1. System packages
sudo apt update
sudo apt install -y python3-venv python3-pip nginx postgresql redis-server git

# 2. PostgreSQL
sudo -u postgres psql -c "CREATE DATABASE lab_db;"
sudo -u postgres psql -c "CREATE USER lab_user WITH PASSWORD 'strong-password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE lab_db TO lab_user;"

# 3. App
cd /home/ubuntu
git clone <your-repo-url> bruteforce-lab && cd bruteforce-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt "psycopg[binary]"

# 4. Environment (production)
cp .env.example .env      # then edit:
#   DJANGO_SETTINGS_MODULE=config.settings.prod
#   DEBUG=False
#   SECRET_KEY=<generated>
#   ALLOWED_HOSTS=mylab.example.com
#   CSRF_TRUSTED_ORIGINS=https://mylab.example.com
#   DATABASE_URL=postgres://lab_user:strong-password@127.0.0.1:5432/lab_db
#   REDIS_URL=redis://127.0.0.1:6379/0
chmod 600 .env

# 5. Migrate, seed, collect static
export DJANGO_SETTINGS_MODULE=config.settings.prod
python manage.py migrate
python manage.py seed_wordlists
python manage.py collectstatic --noinput
python manage.py createsuperuser

# 6. systemd service (Daphne)
sudo cp deploy/bruteforce-lab.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bruteforce-lab

# 7. Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/bruteforce-lab
sudo ln -s /etc/nginx/sites-available/bruteforce-lab /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 8. TLS (Let's Encrypt)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d mylab.example.com
```

Open ports **80** and **443** in the Lightsail firewall. Redeploys:
`./deploy/update.sh`.

**Docker alternative** (full stack locally or on a host):

```bash
export SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key as k; print(k())")
docker compose up --build
# then: docker compose exec web python manage.py seed_wordlists
#       docker compose exec web python manage.py createsuperuser
```

## 15. Security design decisions

- **Target password never stored in plaintext.** Chosen server-side with a
  CSPRNG and stored only as a Django password hash; verified with
  `check_password`. No API/template/WebSocket ever returns it.
- **Student isolation.** Per-lab **read/management** endpoints and pages resolve
  the lab via `get_owned_lab`, returning **404** for non-owners (existence is not
  leaked) — including the `passwords.txt` download and the live monitor.
  WebSocket subscriptions are authorized against ownership; each lab has its own
  Channels group, so events never cross labs. The **training login** endpoint is
  authorized by the secret, unguessable per-student token instead (a capability),
  so the standalone script needs no login; attempts remain fully attributable via
  the lab and are logged with IP + user-agent.
- **`lab_token` is unguessable and immutable.** 24 random URL-safe bytes;
  read-only in serializers and admin — a student cannot repoint a lab.
- **Concurrency safety.** Attempt processing takes a `SELECT ... FOR UPDATE`
  lock inside an atomic transaction, so `max_attempts` cannot be bypassed by
  parallel requests. A unique `(lab, attempt_number)` constraint guarantees no
  duplicate/lost attempts. (Verified by a 40-thread test.)
- **No external targets — by construction.** There is no endpoint that accepts a
  URL. The app cannot fetch, proxy, or forward requests anywhere.
- **Intentional vs. infrastructure controls.** Inside a lab there is no password
  rate-limiting (the exercise). Around it: DRF throttling (`lab_login`,
  `lab_api` scopes), a 512 KB request-body cap, per-lab attempt caps, lab
  expiry, CSRF on all browser forms, and hardened production settings (HTTPS
  redirect, HSTS, secure cookies, nosniff, `X-Frame-Options: DENY`).
- **Role gating.** Instructor access requires **both** `role=INSTRUCTOR` **and**
  `is_staff` — a single flipped field cannot escalate a student. Registration
  always creates a locked-down student.
- **Password visibility policy.** Candidate values are masked by default
  (`p*******`). Full values can be enabled (`SHOW_FULL_CANDIDATE_PASSWORDS`)
  only within the student's own isolated lab and are labelled training data.

## 16. API documentation

The read/management endpoints require an authenticated session and are
owner-only (staff may access any lab); non-owners receive **404**. The training
**login** endpoint is the exception: it is authorized by the secret lab token
alone (see below) so students can run a plain standalone script.

### `POST /api/labs/start/`
Create a new isolated lab for the caller. Body (optional):
`{"difficulty": "EASY" | "MEDIUM" | "HARD"}`. → **201** with the lab (token,
username, `login_url`, counters, expiry).

### `GET /api/labs/<lab_token>/`
Lab detail for its owner (status, counters, `login_url`, latest attempt).
Never includes the target password.

### `GET /api/labs/<lab_token>/wordlist/`
The wordlist assigned to this lab (name, difficulty, passwords, size).

### `GET /api/labs/<lab_token>/attempts/`
The lab's attempt history (attempt number, username, masked/full password,
result, timestamp), oldest first.

### `POST /api/labs/<lab_token>/login/`  — the training endpoint
**Token-only** (no session/login or CSRF needed — the secret lab token is the
credential), so a standalone script can hit it directly. Body:
`{"username": "...", "password": "..."}`.

| Result                | HTTP | `message`                    |
|-----------------------|------|------------------------------|
| Correct password      | 200  | `Authentication successful`  |
| Wrong password        | 401  | `Invalid credentials`        |
| Attempt limit reached | 429  | `Lab attempt limit reached.` |
| Lab expired           | 410  | `This lab has expired.`      |
| Lab disabled          | 403  | `This lab has been disabled.`|
| Already completed      | 409  | `Lab already completed.`     |

Response body (example):

```json
{ "success": false, "message": "Invalid credentials", "attempt_number": 4,
  "attempt_count": 4, "max_attempts": 100, "status": "ACTIVE" }
```

Every attempt is logged and broadcast to the lab's live monitor
(`ws://<host>/ws/labs/<lab_token>/`).

---

## Running the tests

```bash
python manage.py test
```

Covers lab creation, the login flow (success/failure/completion), attempt
numbering, max-attempt enforcement, expiry, **student isolation**, the REST
endpoints, role gating, password masking, and a **40-thread concurrency test**
proving `max_attempts` cannot be bypassed.

## Project layout

```
config/            # settings (base/dev/prod), urls, asgi, wsgi
apps/
  core/            # home page, health check, context processors
  accounts/        # custom User, auth views/forms
  labs/            # Wordlist + Lab, services, REST API, HTML pages, admin
  attempts/        # Attempt, login service, WebSocket consumer/routing
  dashboard/       # student + instructor dashboards
templates/         # Django templates (dark, terminal-inspired UI)
static/            # CSS + JS (copy buttons, live monitor client)
deploy/            # nginx.conf, systemd unit, update.sh
Dockerfile  docker-compose.yml  requirements.txt  .env.example
```
