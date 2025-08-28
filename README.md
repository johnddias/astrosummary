# AstroSummary — UI updates

This repository contains the AstroSummary frontend and backend. Recent updates were made to the Ratio Planner UI (branch `gui`). This top-level README summarizes the changes and how to run the project locally.

## Recent changes (branch: gui)
- RatioPlanner UI: per-filter ratio inputs for Narrowband (Ha, OIII, SII) and Broadband (R, G, B, L).
- Per-filter ratio inputs are persisted to localStorage.
- Narrowband/Broadband toggle checkboxes placed next to their column headers; charts show only selected filter sets.
- Color-scheme selector for charts persisted to localStorage.
- Scan control moved to the sidebar and backend settings persisted (in earlier commits).

## How to run locally

Prerequisites:
- Node.js (compatible version for the Vite + React app)
- Python 3.10+ and the virtualenv dependencies for the backend (see `backend/requirements.txt`)

Frontend (dev):

1. cd `astrosummary-ui`
2. npm install
3. npm run dev

Frontend (build):

1. cd `astrosummary-ui`
2. npm install
3. npm run build

Backend (dev):

1. cd `backend`
2. python -m venv .venv
3. .\.venv\Scripts\Activate.ps1
4. pip install -r requirements.txt
5. uvicorn main:app --reload --host 127.0.0.1 --port 8000

The frontend expects the backend at `http://127.0.0.1:8000` by default when running locally.

