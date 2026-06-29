# AAFC TMS — Setup, Run, and Rollout Guide

**AAFC Training Management System — National Deployable Edition**

This guide explains how to set up, run, test, and roll out the AAFC Training Management System (we will call it "AAFC TMS" or "the system" from here on).

It is written so that a Year 10 student who is confident with computers can follow it, while still being accurate enough for a developer or system administrator. Every technical word is explained in plain English the first time it is used. You do **not** need to have read any other document first — everything you need is here.

Take your time. Read each step, run it, check the **Expected result**, and only move on when it works.

---

## Table of contents

1. Plain-English overview
2. Required software and hardware (Resources required)
3. Folder structure explanation
4. How to download or copy the project
5. How to run the backend locally (without Docker)
6. How to run the frontend locally
7. How to run backend and frontend together
8. How to test login
9. How to check whether the backend is working
10. How to check whether the frontend is working
11. Common problems and fixes
12. Developer workflow
13. User workflow
14. Local demo rollout
15. Pilot rollout
16. Production-like rollout
17. Backup and restore
18. Security and data governance checklist
19. Go / no-go checklist
20. Rollback plan
21. Support handover checklist
22. Glossary

---

## 1. Plain-English overview

AAFC TMS is a tool that helps an Air Force Cadets squadron plan and track its training. It records parade nights (the regular training evenings), the sessions taught on those nights, who taught them, whether each session actually happened, and reports that summarise all of this.

The system has **two main parts** that work together:

**1. The backend — the engine.**
The backend is the part you do not see directly. It is like the engine of a car. It stores all the data, checks the access code when someone logs in, decides who is allowed to see or change what, keeps a permanent history (the "audit log") of important actions, and hands data to the website when asked. The backend already exists and runs on your computer at the address `http://localhost:8000`.

> **API** means "Application Programming Interface." It is simply the set of doorways the backend offers so the website (or a developer) can ask for data or send data. Think of it as the service counter where the website places its orders.

**2. The frontend — the website you click through.**
The frontend is the normal dashboard that users open in a web browser. It has the login screen, the menus, the buttons, and the tables. It does **not** store the real data itself. Instead, every time it needs information, it asks the backend through the API. This matters because the backend is the part that keeps data safe and applies the rules.

> **Important:** There is an old standalone HTML prototype that stores everything inside the browser. **That old prototype is not the real system.** It may be used only as a picture of what the screens should look like. It is not secure and must not be used for real cadet or staff data. The real frontend (in the `frontend/` folder) always talks to the backend.

**Why two parts?** Keeping the engine (backend) separate from the dashboard (frontend) means the rules about who can see what are enforced in one trusted place (the backend), not in the browser where they could be bypassed.

---

## 2. Required software and hardware (Resources required)

This section lists what you need. There are three different audiences: the **developer** (the person running commands), the **production server** (the computer that hosts the system for a pilot), and the **normal user** (staff who just log in).

### 2.1 Developer machine (the computer you set things up on)

**Minimum:**

- A modern Mac, Windows, or Linux computer.
- 8 GB of RAM (the computer's short-term memory).
- 10 GB of free disk space (storage).
- Python 3.11 or newer (the language the backend is written in).
- Node.js LTS (the tool that runs the frontend; "LTS" means "Long-Term Support", the stable version).
- npm (comes with Node.js; it downloads frontend packages).
- Git (a tool for copying and tracking code).
- A modern browser: Chrome, Edge, Firefox, or Safari.

**Recommended:**

- 16 GB of RAM.
- 20 GB of free disk space.
- VS Code (Visual Studio Code) or a similar code editor.
- Docker Desktop (optional; explained later — it packages the app so it runs the same way everywhere).
- A stable internet connection for downloading packages the first time.

### 2.2 Production server (for a real pilot)

> **Server** means a computer, usually running all the time in a data centre or cloud, that hosts the system for other people to use over the internet.

**Small pilot (one or a few squadrons):**

- 2 vCPU (virtual processor cores).
- 4 GB RAM.
- 40 GB disk.
- Ubuntu LTS server (a stable version of the Linux operating system).
- Docker and Docker Compose installed.
- A public domain name (for example `tms.example.org`).
- HTTPS enabled through Caddy (HTTPS is the secure, padlocked version of web traffic; Caddy is the web server that provides it).
- Daily backups.

**Larger Wing rollout:**

- 4 vCPU.
- 8–16 GB RAM.
- 80–160 GB disk.
- The PostgreSQL data stored on reliable storage (PostgreSQL is the production database; a database is an organised store of data).
- Monitoring and log collection (so you can see how the system is behaving).
- A tested backup **and** restore process.
- Controlled administrator access (only a few trusted people).

### 2.3 Normal user (staff who log in)

- A modern web browser.
- A stable internet connection.
- **No software to install** — the deployed system is just a website.
- A login access code issued by authorised staff.
- Access only to what their role allows.

---

## 3. Folder structure explanation

When you open the project folder `aafc-tms-national`, you will see something like this:

```
aafc-tms-national/
  backend/          The engine: FastAPI app, data models, tests, manage.py
  frontend/         The website: React/TypeScript app (the real dashboard)
  deployment/       Scripts and config for running on a server (backups, migrations, smoke test)
  docs/             Extra documentation
  README.md         Short project overview
  DEPLOYMENT.md     Notes on deploying
  SECURITY.md       Security notes
  TESTING.md        Testing notes
  DATA_GOVERNANCE.md  Rules about what data may be stored
  docker-compose.yml       Recipe to run a simple demo with Docker (SQLite)
  docker-compose.prod.yml  Recipe to run a production-like stack with Docker
  .env.example      A template for secret settings (copy it to make .env)
  Makefile          Shortcuts for common commands
```

You will spend most of your time in two folders:

- `backend/` — where you start the engine.
- `frontend/` — where you start the website.

> **What is `frontend/`?** It is the real React/TypeScript dashboard. "React" and "TypeScript" are just the tools the website is built with. This folder is the source of truth for the user interface. The old standalone HTML prototype is **not** in here and is **not** used for real data.

---

## 4. How to download or copy the project

You need a copy of the `aafc-tms-national` folder on your computer.

**If you were given a zip file:** unzip it. You should end up with a folder named `aafc-tms-national` containing the structure shown above.

**If you were given a Git repository address:** open your terminal and run the command below.

> **Terminal** means the text window where you type commands instead of clicking buttons. On a Mac it is called "Terminal"; on Windows you can use "PowerShell" or "Windows Terminal"; on Linux it is usually "Terminal" too.

```bash
git clone <REPOSITORY_ADDRESS> aafc-tms-national
```

**What this does:** `git clone` makes a complete copy of the project from the repository onto your computer, into a folder named `aafc-tms-national`.

**Expected result:** a new folder called `aafc-tms-national` appears, containing `backend/`, `frontend/` (if included), `deployment/`, and the other files.

**If it fails:** the message `command not found: git` means Git is not installed. Install Git first (search "install Git" for your operating system), then try again.

Now move into the project folder:

```bash
cd aafc-tms-national
```

**What this does:** `cd` means "change directory" — it moves you **into** the folder so the next commands run in the right place.

---

## 5. How to run the backend locally (without Docker)

This section starts the engine on your own computer. "Locally" means "on this computer, not on the internet."

Open a terminal and run these commands **one at a time**, checking each works before the next.

### Step 5.1 — Move into the backend folder

```bash
cd aafc-tms-national/backend
```

**What this does:** moves you into the `backend` folder, where the engine lives.

### Step 5.2 — Create a private Python toolbox (virtual environment)

```bash
python3 -m venv .venv
```

**What this does:** creates a `.venv` folder. A **virtual environment** (`.venv`) is a private toolbox of Python tools just for this project, so it does not clash with anything else on your computer.

**If it fails:** if `python3` is "command not found", try `python` instead. If neither works, install Python 3.11 or newer.

### Step 5.3 — Turn the toolbox on (activate it)

```bash
source .venv/bin/activate
```

**What this does:** switches your terminal to use the project's private toolbox. You will usually see `(.venv)` appear at the start of your terminal line, which tells you it is on.

> **On Windows** the activate command is slightly different: `.venv\Scripts\activate`.

**Why it matters:** without activating, the next command might install tools in the wrong place.

### Step 5.4 — Install the backend tools

```bash
pip install -r requirements.txt
```

**What this does:** `pip` is Python's installer. `-r requirements.txt` tells it to install exactly the list of tools the backend needs. This may take a minute the first time.

**Expected result:** lots of lines scroll past ending without an error, and you get your terminal prompt back.

**If it fails:** check your internet connection (the tools download from the internet) and that the toolbox is active (Step 5.3).

### Step 5.5 — Create demo data (seed)

```bash
python manage.py --seed
```

**What this does:** "seeding" fills the database with realistic demo data — the National HQ, 7 Wing, 16 squadrons, demo access codes, curriculum, and some 703 Squadron example sessions. This gives you something to log in to and look at.

> For local demo use, the backend stores this in **SQLite**, a simple single-file database that needs no setup. For production you use **PostgreSQL** instead (covered later).

**Expected result:** a message confirming the demo data was created.

### Step 5.6 — Start the backend server

```bash
python manage.py
```

**What this does:** starts the engine. It now listens for requests at `http://localhost:8000`.

**Expected result:** the terminal shows startup messages and then appears to "pause" — that is normal; it is now running and waiting.

> **Mac note (important):** Do **not** use `python manage.py --reload` as your everyday command on a Mac. The `--reload` option watches files for changes and can get stuck in a restart loop when it watches the `.venv` toolbox. Just use `python manage.py`.

> **Keep this window open.** The backend runs only while this terminal window stays open. If you press **CTRL + C**, the backend stops. To use the system you must leave it running.

---

## 6. How to run the frontend locally

The frontend is the website users click through. It needs its own terminal window (leave the backend running in the first one).

### Step 6.1 — Open a second terminal and move into the frontend folder

```bash
cd aafc-tms-national/frontend
```

**What this does:** moves into the website's folder.

### Step 6.2 — Tell the frontend where the backend is (the `.env` file)

> An **`.env` file** ("environment file") is a small text file that holds settings, such as addresses and secrets, kept separate from the code.

Copy the example settings file to a real one:

```bash
cp .env.example .env
```

**What this does:** makes a working settings file called `.env` from the provided template.

Open `.env` and make sure it contains this line:

```
VITE_API_BASE_URL=http://localhost:8000
```

**What this means:** it tells the website that the backend (the engine) is at `http://localhost:8000`. If this address is wrong, the website will not be able to load any data.

### Step 6.3 — Download the frontend packages

```bash
npm install
```

**What this does:** `npm install` downloads all the building blocks the website needs into a `node_modules` folder. This can take a few minutes the first time.

**Expected result:** it finishes without errors and you get your prompt back.

**If it fails:** `npm: command not found` means Node.js is not installed — install Node.js LTS, then try again.

### Step 6.4 — Start the website

```bash
npm run dev
```

**What this does:** starts the frontend in "development mode" and serves it at `http://localhost:5173`.

**Expected result:** the terminal prints a local address, usually `http://localhost:5173`. Open that in your browser and you should see the login screen.

> **Keep this window open too.** Like the backend, the website runs only while this terminal stays open.

---

## 7. How to run backend and frontend together

For the full system you need **two terminal windows open at the same time**:

- **Terminal 1 — backend:** in `aafc-tms-national/backend`, with the toolbox active, running `python manage.py`.
- **Terminal 2 — frontend:** in `aafc-tms-national/frontend`, running `npm run dev`.

The order that works most reliably:

1. Start the backend first (Section 5). Wait until `http://localhost:8000/api/health` works (Section 9).
2. Then start the frontend (Section 6).
3. Open `http://localhost:5173` in your browser.

**Why this order matters:** the website expects the engine to be ready. If the backend is not running, the website will show a connection error instead of data.

---

## 8. How to test login

There are two ways to test login: through the backend's built-in testing page (Swagger) and through the real website.

> **Swagger** is a web page the backend provides at `/docs`. It lists every API doorway and lets you try them out by filling in a form. It is meant for developers and testers, not normal users.

### 8.1 Swagger method (tests the backend directly)

1. Open `http://localhost:8000/docs` in your browser.
2. Find and click **POST /api/auth/login**.
3. Click **Try it out**.
4. In the box, enter this JSON (text in a structured format):

   ```json
   {
     "code": "ADMIN703"
   }
   ```

5. Click **Execute**.
6. **Expected result:** a response with a success status and a `token` (a temporary key that proves you are logged in).
7. If you want to try other protected doorways in Swagger, copy the token, click the **Authorize** button near the top, and enter:

   ```
   Bearer TOKEN_HERE
   ```

   (Replace `TOKEN_HERE` with the token you copied. "Bearer" is just the required word in front of it.)

**If it fails:** a 401 or "invalid code" message means the code was wrong or the demo data was not seeded — re-run `python manage.py --seed`.

### 8.2 Frontend method (tests the real website)

1. Open `http://localhost:5173`.
2. Enter an access code (for example `ADMIN703`) and log in.
3. **Expected result:** the dashboard loads.
4. Confirm your **role** and **unit/scope** appear in the top header.
5. Confirm the data is coming from the backend, not the browser: refresh the page (press F5). If the data is still there after refreshing and came back from the server, that is correct. (If data only existed until you refreshed, something is wrong — see Section 11.)

### 8.3 Demo access codes — **DEMO ONLY**

> **These are demonstration codes for local testing only. They are not production credentials. In any real deployment they MUST be changed before anyone uses the system.**

All seeded demo codes (7 Wing pilot dataset):

| Code | Role | Scope |
|---|---|---|
| `SYSADMIN2026` | System Admin | Full system |
| `ADMINNATIONAL` | National Admin | AAFC National HQ |
| `NATIONAL2026` | National Viewer | AAFC National HQ |
| `AUDITOR2026` | Auditor | All wings / squadrons |
| `ADMIN7WG` | Wing Admin | 7 Wing (WA) |
| `7WG2026` | Wing Viewer | 7 Wing (WA) |
| `ADMIN703` | Squadron Admin | 703 Squadron — demo unit |
| `703SQN2026` | Squadron General | 703 Squadron — demo unit |
| `ADMIN{code}` | Squadron Admin | e.g. `ADMIN701`, `ADMIN704` … `ADMIN723` |
| `{code}SQN2026` | Squadron General | e.g. `701SQN2026`, `704SQN2026` … |

> **System Admin note:** The `SYSADMIN2026` code provides the highest level of access. It can create Wings, national accounts, and system-level accounts. Use it only for initial system setup and testing. Disable or replace this account before any real-world deployment.

Do not treat these as secrets and do not ship them to production. Section 18 explains how access codes must be handled for real use.

---

## 9. How to check whether the backend is working

The backend provides simple "health check" doorways. A **health check** is a page that answers "are you alive and ready?"

Open these in your browser (with the backend running):

- `http://localhost:8000/api/health`
  **Expected result:** a small JSON response such as `{"status":"ok"}`. This means the backend process is alive.

- `http://localhost:8000/api/health/ready`
  **Expected result:** a JSON response indicating the backend is ready to serve, including that it can reach its database.

- `http://localhost:8000/docs`
  **Expected result:** the Swagger testing page loads.

**If `/api/health` fails:** the backend is not running, or another program is using port 8000 (see Section 11).

**If `/docs` is blank but `/api/health` works:** the backend itself is fine. Check `http://localhost:8000/openapi.json` — if that shows text/JSON, only the Swagger page styling is blocked (a security setting called CSP). The backend is healthy; just use `/openapi.json` or fix the Swagger/CSP config later.

---

## 10. How to check whether the frontend is working

With both parts running:

1. Open `http://localhost:5173`. **Expected result:** the login screen appears.
2. Log in with a demo code. **Expected result:** the dashboard loads with real numbers and tables.
3. Click around the menu (Dashboard, Calendar, Parade Nights, Curriculum, Reports). **Expected result:** each page loads data.
4. Refresh the browser. **Expected result:** you stay logged in (or are asked to log in again if the session expired) and the data reloads **from the backend**.

**If the website loads but shows a connection error:** the backend is probably not running, or `VITE_API_BASE_URL` is wrong — see Section 11.

---

## 11. Common problems and fixes

**Problem: `Address already in use`**
Meaning: another program is already using the port (8000 for backend, 5173 for frontend).
Fix:

```bash
lsof -i :8000
```

This lists what is using port 8000 (use `:5173` for the frontend). Stop that program, or start the backend on a different port. On Windows use `netstat -ano | findstr :8000` instead.

**Problem: Backend works but the frontend cannot connect.**
Possible causes:

- The backend is not running.
- `VITE_API_BASE_URL` in the frontend `.env` is wrong.
- CORS is not allowing the frontend address. ("**CORS**" is a browser safety rule that controls which websites may talk to the backend. The backend must list `http://localhost:5173` as allowed — it already does by default for local development.)
- The login session/token has expired.
- The API path is wrong.

**Problem: Swagger (`/docs`) is a blank page.**
Possible cause: a Content Security Policy (CSP — a browser security rule) is blocking the Swagger page's files.
Fix: open `http://localhost:8000/openapi.json`. If that loads, the backend is fine and only the Swagger page needs its CSP/asset settings adjusted.

**Problem: `command not found: python`**
Fix: try `python3` instead. If neither works, install Python 3.11+.

**Problem: `npm: command not found`**
Fix: install Node.js LTS (npm comes with it), then try again.

**Problem: Login works in Swagger but not on the website.**
Fix: open the browser's developer tools (right-click → Inspect), check the **Console** and **Network** tabs for red errors. Common causes: CORS, cookie settings, or the wrong `VITE_API_BASE_URL`.

**Problem: `403 forbidden`.**
Meaning: this is the backend **protecting** data — that is a good thing, not a crash. It usually means the wrong role, the wrong squadron, or that Proxy Mode / Intervention Mode is required first (see Section 13). The website should show a clear "access not permitted" or "proxy required" message rather than the raw error.

**Problem: Data disappears after you refresh the page.**
Meaning: the website is wrongly keeping data only in the browser instead of getting it from the backend. Real data must come from the backend every time. If you see this with the real `frontend/`, report it as a bug.

---

## 12. Developer workflow

This is the routine for a developer who is changing or checking the code.

**Backend tests:**

```bash
cd aafc-tms-national/backend
source .venv/bin/activate
pytest -q
```

**What this does:** `pytest` runs the backend's automated tests, which check that the rules (login, permissions, reports, audit, and so on) still work. `-q` means "quiet" (shorter output).
**Expected result:** a line such as `39 passed`.
**If it fails:** stop and fix the failing test before adding new features. Do not weaken a test just to make it pass.

**Frontend type-check and tests:**

```bash
cd aafc-tms-national/frontend
npm run typecheck
npm run test
npm run test:e2e
npm run build
```

**What each does:**

- `npm run typecheck` checks the TypeScript code for type mistakes without running it.
- `npm run test` runs the frontend's small unit tests (for example, that buttons and helpers behave correctly).
- `npm run test:e2e` runs "end-to-end" tests with Playwright: a robot browser logs in and clicks through pages to confirm the whole flow works. This needs the backend and frontend running.
- `npm run build` creates the final, optimised version of the website in a `frontend/dist` folder, ready to deploy.

**Expected result:** each command finishes without errors; `build` produces a `dist` folder.

**Golden rules for developers:**

- The backend is the security authority. Never move permission checks into the frontend only.
- Never store the real, trusted data in the browser.
- Never put access codes or secrets in the frontend code.
- Keep the audit log read-only from the user interface.

---

## 13. User workflow

This describes what each kind of user does. The exact buttons a person sees depend on their role, because the backend only allows permitted actions.

### Squadron Admin

1. Log in.
2. View the dashboard (readiness, sessions, coverage, action items).
3. View the curriculum and Learning Hub links.
4. Create a parade night.
5. Create a session on that parade night.
6. Set a session's status (for example **delivered**, or **not delivered** with a reason).
7. View reports.
8. Add an action item.
9. Preview and commit a cadet import (and roll it back if needed).
10. Check the audit trail if authorised.

### Squadron General

1. Log in.
2. View the squadron training information they are permitted to see.
3. They do **not** see admin "write" controls unless the backend allows it for their role.

### Wing Admin

1. Log in.
2. View the Wing overview (all squadrons in the wing).
3. Enter **Proxy Mode** for a squadron, giving a **reason**. (Proxy Mode lets a wing officer act on a squadron's behalf; the reason is required and recorded.)
4. Perform an authorised support action.
5. Exit Proxy Mode.
6. Confirm the proxy banner disappears.
7. Confirm the audit log recorded the action and the reason.

### National Admin

1. View the National overview (all wings).
2. Where implemented, use **Delegated Intervention Mode** to act below national level, always with a reason.
3. The system must **not** allow silent editing of wing or squadron data without a recorded reason.

### Auditor

1. View the audit log.
2. There are **no** edit controls — this role is read-only by design.

---

## 14. Local demo rollout

This is the first and safest stage: prove everything runs on one computer.

- **Purpose:** show that the backend and frontend start and talk to each other.
- **Data:** demo data only (from `--seed`). No real cadet or staff information.
- **Users:** just the developer or tester.
- **Steps:** follow Sections 5–10. Confirm health checks pass, login works, and the dashboard loads.

This stage needs no server, no domain name, and no Docker.

---

## 15. Pilot rollout

A **pilot** is a small, careful real-world trial. Roll out in stages and do not skip ahead.

**Stage 1 — Developer local setup.** Prove the system runs on one computer with demo data. Users: developer/tester only.

**Stage 2 — Internal demo.** Show staff the workflow using fake/demo data only, with a small trusted group. Collect feedback.

**Stage 3 — 703 Squadron pilot.** Trial with one squadron, using only approved low-risk training-planning data. Users: authorised staff. Controls: daily backups, regular audit-log review, and an issue log to record problems.

**Stage 4 — Multi-squadron 7 Wing pilot.** Add a few squadrons plus wing training staff. Test wing-level visibility, Proxy Mode, and reports with approved training-coordination data.

At every stage, review: did access control behave correctly? Were backups taken? Did anything confuse users? Fix issues before widening.

---

## 16. Production-like rollout

"Production-like" means running the system the way it would run for real users, using Docker for consistency.

> **Docker** packages the app and everything it needs into containers so it runs the same way on any server. **Docker Compose** runs several containers together from one recipe file.

### 16.0 The preferred model: same domain (use this for the first pilot)

In production, the **frontend and the backend live on the same web address (domain)**. Staff open one URL and never see anything about ports or servers:

- Frontend (the website): `https://tms.yourdomain.org/`
- Backend API (the doorways): `https://tms.yourdomain.org/api/...`

A single public web server, **Caddy**, sits in front and does two jobs:

1. It serves the built website files (`frontend/dist`) at `/`.
2. It forwards any request starting with `/api/` to the backend container.

Because both come from the same domain, you avoid a whole category of cross-site problems (cookie, CORS, CSRF, and SameSite headaches). **This is why the same-domain model is the default and the first pilot option.**

Two more things Caddy must do, both already configured in this project:

- **HTTPS** (the secure padlock) — Caddy provisions this automatically once your domain points at the server.
- **React Router refresh support** — the website uses addresses like `/dashboard` and `/reports`. If a staff member refreshes the page on `/reports`, Caddy must still return the website's main file (`index.html`) so the app can re-open that page. This "fall back to index.html" rule is built into the Caddy config.

**Frontend setting for the same-domain model.** Because the website and API share a domain, the frontend should call the API using **relative `/api/...` paths**. In the frontend `.env`, leave the base URL **empty**:

```
VITE_API_BASE_URL=
```

Do **not** hard-code `http://localhost:8000` or any public `:8000` address into the production website. (If your build genuinely needs an absolute address, use your real domain: `VITE_API_BASE_URL=https://tms.yourdomain.org`.)

**The Caddy rule that makes this work** (already in `deployment/caddy/Caddyfile`; just change the domain):

```
tms.yourdomain.org {
    encode gzip
    handle /api/* {
        reverse_proxy backend:8000
    }
    handle {
        root * /srv/frontend
        try_files {path} /index.html
        file_server
    }
}
```

In plain words: `/api/...` goes to the backend; everything else serves the website, and unknown paths fall back to `index.html` so refreshes work.

> **Separate hosting is an advanced option only.** You *can* host the website separately (Netlify, Vercel, Cloudflare Pages, or an S3 bucket) and point it at the backend's public URL. But that splits the website and API across two domains, which means you must carefully configure CORS, cookie SameSite, CSRF, and HTTPS. **Do not choose this for the first pilot** unless there is a strong reason.

### 16.1 Simple Docker demo (still SQLite)

```bash
cd aafc-tms-national
docker compose up --build
```

**What this does:** builds and starts a simple demo using SQLite, exposing the backend on port 8000.
**Expected result:** `http://localhost:8000/api/health` works.

### 16.2 Production-like stack (PostgreSQL + Redis + Caddy)

**Step 1 — create your real settings file:**

```bash
cd aafc-tms-national
cp .env.example .env
```

**What this does:** makes a `.env` file from the template. **You must edit `.env` before production-like use** — the defaults are not safe for real use.

**Step 2 — set, at minimum, these values in `.env`:**

- `ENVIRONMENT=production`
- `COOKIE_SECURE=true` (only send the login cookie over secure HTTPS).
- `SECRET_KEY` — a long random secret used by the backend.
- `JWT_SECRET` — a long random secret used to sign login tokens.
- `POSTGRES_PASSWORD` — a strong password for the database.
- `DATABASE_URL` — where the database is (points at PostgreSQL).
- `CORS_ALLOWED_ORIGINS` — set this to your real website address only.
- Your production domain name (for HTTPS).

Use long, random values for the secrets and password. Never reuse the example values.

**Step 3 — build the website first (so Caddy has something to serve):**

```bash
cd frontend
npm install
npm run build
cd ..
```

**What this does:** `npm run build` creates the optimised website files in `frontend/dist/`. In the same-domain model, Caddy serves this folder at `/`. The production compose mounts `frontend/dist` into Caddy automatically, so this folder must exist before you start the stack.
**Expected result:** a `frontend/dist/` folder appears containing `index.html` and an `assets/` folder.

**Step 4 — start the production-like stack:**

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

**What this does:** starts four parts together:

- **PostgreSQL** — the production database that stores the real data.
- **Redis** — an in-memory helper used for rate limiting, caching, and future background jobs.
- **Backend** — the engine. Note: it is **not** exposed to the public; only Caddy can reach it.
- **Caddy** — the **only public** web server. It provides HTTPS, serves the website from `frontend/dist`, and forwards `/api/*` to the backend. It is the single public entry point on ports 80 and 443.

The `-d` means "detached" — it runs in the background.

**Step 5 — apply database migrations:**

```bash
bash deployment/scripts/run_migrations.sh
```

**What this does:** a **migration** updates the database's structure (its tables and columns) to match what the current code expects. Running migrations makes sure the database is the right shape before anyone uses it.

**Step 6 — run a smoke test:**

```bash
bash deployment/scripts/smoke_test.sh https://tms.yourdomain.org
```

**What this does:** a **smoke test** is a quick check of the most important things — health, login, a data request, and (for a real domain) that the website is served at `/`. Replace `https://tms.yourdomain.org` with your real address.
**Expected result:** the script reports success for the basic checks, including `index.html OK`.

**Step 7 — open the public URL and test.** Open `https://tms.yourdomain.org`, log in, and walk through a few key workflows (dashboard, create a parade night, set a session status, view a report).

### 16.3 Deployment flow (summary) and recommended commands

The whole production deployment, in order:

1. Build the frontend (`cd frontend && npm install && npm run build`).
2. Make sure `frontend/dist/` is in place (the prod compose mounts it into Caddy).
3. Start the production Docker stack.
4. Run migrations.
5. Run the smoke test.
6. Open the public URL.
7. Log in and test the key workflows.

Recommended production deployment commands (after building the frontend and editing `.env`):

```bash
docker compose -f docker-compose.prod.yml up --build -d
bash deployment/scripts/run_migrations.sh
bash deployment/scripts/smoke_test.sh https://tms.yourdomain.org
```

**Important production safety rules:**

- Caddy is the **only** public entry point (ports 80 and 443). Do not expose the backend's port 8000 to the public.
- Do not expose PostgreSQL or Redis to the public.
- Do not expose the Swagger `/docs` page publicly unless it has been explicitly approved.
- In the production website, do not hard-code `http://localhost:8000` or a public `:8000` URL — use the empty (relative) base or your real domain.

### 16.4 Before real staff use — final pre-flight list

Tick all of these before any real staff log in:

1. Change all demo access codes.
2. Set strong production secrets (`SECRET_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`).
3. Confirm HTTPS works.
4. Confirm `COOKIE_SECURE=true`.
5. Confirm CORS allows only the real domain.
6. Confirm backend port 8000 is **not** public.
7. Confirm PostgreSQL and Redis are **not** public.
8. Run migrations.
9. Run smoke tests.
10. Run backend tests (`cd backend && pytest -q`).
11. Run frontend tests (`cd frontend && npm run test`).
12. Test login and logout.
13. Test role scoping (users see only their own scope).
14. Test Wing Proxy Mode (enter with reason, banner shows, exit clears it).
15. Test that audit log entries are recorded for write actions.
16. Test a backup.
17. Test a restore.
18. Confirm no real sensitive data is used before governance approval.

---

## 17. Backup and restore

A **backup** is a saved copy of the data you can return to if something goes wrong. A **restore** puts a backup back into the database.

**Make a backup:**

```bash
bash deployment/scripts/backup_postgres.sh
```

**What this does:** creates a compressed copy of the PostgreSQL database (a `.sql.gz` file) in the backups folder.

**Restore from a backup:**

```bash
bash deployment/scripts/restore_postgres.sh backups/FILE.sql.gz
```

**What this does:** loads the chosen backup file back into the database. Replace `FILE.sql.gz` with the actual backup filename.

> **Test your restore before you rely on it.** A backup you have never restored is not a backup you can trust. Practise restoring into a test environment so you know it works and how long it takes.

---

## 18. Security and data governance checklist

> **Governance** means the rules about what data may be stored and how it must be handled.

**What this system is for:**

- AAFC TMS supports training **planning, coordination, and reporting**.
- It does **not** replace CEA, CadetNet, or any authorised AAFC/Defence system of record. It is a planning aid, not the official record.

**Data rules:**

- Do **not** store unnecessary medical, parent/carer, or personal contact information.
- Do **not** upload sensitive data unless it is authorised.
- Support notes must be **admin-only** and **audited** (every view/change recorded).
- The audit log must be **read-only** from the user interface — no editing or deleting.
- Imports must use **approved, user-exported data only**.

**Security rules:**

- Change all demo access codes before real use.
- Keep secrets (`SECRET_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`) long, random, and private.
- Use HTTPS in production (`COOKIE_SECURE=true`).
- Lock `CORS_ALLOWED_ORIGINS` to the real website only.
- Never put access codes or secrets in the frontend.
- Keep the database, Redis, and backend port off the public internet.

---

## 19. Go / no-go checklist

Only go live when **every** box is true. Tick each one:

- [ ] Backend starts.
- [ ] Frontend starts.
- [ ] Health checks pass (`/api/health` and `/api/health/ready`).
- [ ] Login works.
- [ ] Logout works.
- [ ] The user's role is displayed correctly.
- [ ] Squadron scoping works (users see only their squadron's data).
- [ ] Wing Proxy Mode works (enter with reason, banner shows, exit clears it).
- [ ] Parade night creation works.
- [ ] Session status update works (including "not delivered" with a reason).
- [ ] Reports load.
- [ ] Imports preview safely (formula-injection neutralised) and require preview before commit.
- [ ] Audit records write actions.
- [ ] Backup works.
- [ ] Restore has been tested.
- [ ] HTTPS works.
- [ ] CORS is locked to the production domain.
- [ ] No demo access codes remain in production.
- [ ] No public database or Redis port.
- [ ] No real sensitive data is used before governance approval.

If any box is unticked, the answer is **no-go**. Fix it first.

---

## 20. Rollback plan

If a new version causes problems, calmly return to the last working state:

1. **Stop the new version.** Shut down the new containers or process so it stops making things worse.
2. **Restore the previous version.** Switch back to the last known-good code or container image (for example, the previous Git commit).
3. **Restore the database backup** if the data was changed or corrupted (Section 17).
4. **Test health.** Confirm `/api/health` and `/api/health/ready` pass.
5. **Test login.** Confirm a normal user can log in.
6. **Record what happened** in a deployment log: what changed, what broke, and what you did. This helps prevent a repeat.

---

## 21. Support handover checklist

Before handing the system to whoever will look after it, write down the answers to all of these:

- Where the code repository is stored (and how to access it).
- Who has administrator access.
- Where the `.env` file (with secrets) is stored and who can read it.
- Where backups are stored.
- How often backups run.
- How to restore a backup (and confirmation it has been tested).
- Who can approve new users / issue access codes.
- Who can approve data imports.
- How to report a bug.
- How to request a new feature.
- How to disable a compromised access code immediately.

A handover is not complete until someone other than the original developer can run, back up, and restore the system using these notes.

---

## 22. Glossary

- **Backend** — the engine; stores data, checks logins, applies rules, provides the API. Runs at `http://localhost:8000`.
- **Frontend** — the website/dashboard users click through; asks the backend for data. Runs at `http://localhost:5173`.
- **API** — the set of doorways the backend offers so the frontend (or a developer) can request or send data.
- **Terminal** — the text window where you type commands.
- **Command** — an instruction you type into the terminal.
- **`cd`** — "change directory"; moves into a folder.
- **Virtual environment (`.venv`)** — a private Python toolbox just for this project.
- **`pip`** — Python's tool for installing Python packages.
- **`npm`** — Node.js's tool for installing frontend packages.
- **Node.js** — the tool that runs the frontend's build and dev server. "LTS" = the stable long-term-support version.
- **Seed** — fill the database with demo data.
- **Database** — an organised store of data. **SQLite** is a simple single-file database for demos; **PostgreSQL** is the stronger database for production.
- **`.env` file** — a small text file holding settings and secrets, kept out of the code.
- **`VITE_API_BASE_URL`** — the setting that tells the frontend where the backend is.
- **CORS** — a browser safety rule controlling which websites may talk to the backend.
- **CSP (Content Security Policy)** — a browser security rule controlling what a page may load; can affect the Swagger page.
- **Swagger / `/docs`** — the backend's built-in page for trying API doorways; for developers/testers.
- **Token** — a temporary key proving you are logged in.
- **Health check** — a page that reports whether the backend is alive and ready.
- **Docker** — packages the app into containers so it runs the same everywhere. **Docker Compose** runs several containers together.
- **Container** — a self-contained package that runs one part of the system.
- **Migration** — a controlled update to the database's structure (its tables and columns).
- **Smoke test** — a quick check of the most important functions after starting or deploying.
- **Caddy** — the public web server that provides HTTPS and forwards requests to the backend.
- **Redis** — an in-memory helper for rate limiting, caching, and background jobs.
- **HTTPS** — the secure, padlocked version of web traffic.
- **Proxy Mode** — lets a Wing officer act on a squadron's behalf, with a required, recorded reason.
- **Delegated Intervention Mode** — lets a National officer act below national level, with a required, recorded reason.
- **Audit log** — a permanent, read-only record of important actions.
- **Backup / Restore** — saving a copy of the data, and putting it back.
- **Production** — the real, live environment that real users use.
- **Governance** — the rules about what data may be stored and how it must be handled.
- **System of record** — the official authoritative source for data (for AAFC that is CEA/CadetNet — **not** this system).

---

*End of guide. Keep this document with the project so anyone — student, staff member, administrator, or developer — can set up, run, and safely roll out AAFC TMS.*
