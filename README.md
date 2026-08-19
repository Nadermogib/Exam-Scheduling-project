# نظام جدولة الامتحانات — Exam Scheduling System

> Conflict-free exam timetabling for supplementary exams ("الدور التكميلي"),
> using Google OR-Tools CP-SAT for an exact, mathematically guaranteed zero-conflict schedule.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.11 |
| pip | 22+ |
| Node.js | 18+ |
| npm | 9+ |

---

## Quick Start

### 1 — Clone / open the project

```
cd "Exam Scheduling project"
```

### 2 — Backend setup

```powershell
cd backend
pip install -r requirements.txt
cd ..
```

### 3 — Generate test fixture (first time only)

```powershell
python fixtures/generate_fixture.py
```

This creates `fixtures/test_fixture.xlsx` — a synthetic file with seeded errors for testing.

### 4 — Start the backend

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

The backend will be available at **http://localhost:8000**.
Interactive API docs: **http://localhost:8000/docs**

### 5 — Start the frontend (separate terminal)

```powershell
cd frontend
npm install      # first time only
npm run dev
```

The app will be available at **http://localhost:5173**.

---

## Smoke Tests

After both servers are running, verify the scaffold:

```powershell
# Backend health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Database status
curl http://localhost:8000/api/db/status
# Expected: {"ok":true,"row_count":0}
```

---

## Project Structure

```
Exam Scheduling project/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── requirements.txt     # Pinned Python dependencies
│   ├── app/
│   │   ├── database.py      # SQLite init & connection helper
│   │   └── routers/
│   │       ├── health.py    # GET /health
│   │       └── db_status.py # GET /api/db/status
│   └── data/                # SQLite DB file lives here (auto-created)
├── frontend/
│   ├── index.html           # RTL + Arabic font setup
│   ├── .env                 # VITE_API_BASE_URL (change to deploy remotely)
│   └── src/
│       ├── main.jsx
│       ├── index.css        # Global design system (RTL + CSS tokens)
│       ├── App.jsx          # Placeholder home screen
│       ├── App.css
│       └── api/
│           └── client.js    # Axios client (reads base URL from .env)
├── fixtures/
│   ├── generate_fixture.py  # Generates test_fixture.xlsx
│   └── test_fixture.xlsx    # Synthetic test data (auto-generated)
├── spec.md                  # Full system specification
└── README.md
```

---

## Environment Variables

### Backend

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed CORS origins |
| `DB_DIR` | `backend/data/` | Directory where the SQLite file is stored |

### Frontend

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL — change this to deploy to a remote server |

---

## Moving to a Hosted Server

The architecture is designed for zero-code-change server migration (AQ-4):

1. Deploy the FastAPI backend to your server.
2. In `frontend/.env`, set `VITE_API_BASE_URL=https://your-server.example.com`.
3. In the backend, set `ALLOWED_ORIGINS=https://your-frontend.example.com`.
4. Run `npm run build` to produce a static bundle; serve it via nginx or equivalent.

No source code changes required.

---

## Development Plan

See [`plan.md`](plan.md) for the full phased implementation plan with task-level checkboxes.
