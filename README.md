# AI Prompt Batch Processing Service

Minimal FastAPI demo that accepts a JSON batch of prompts, processes them concurrently
against an in-process mock inference endpoint, and persists progress/results to SQLite.

Summary
- Persistence: SQLite at data/db.sqlite3 (managed by `app/db.py`).
- Endpoints:
  - `POST /batch` — submit a JSON array of prompt strings; returns `{ "batch_id": "..." }`.
  - `GET /batch/{id}/status` — progress summary (total / completed) read from the DB.
  - `GET /batch/{id}/results` — aggregated prompt results read from the DB.
  - `POST /mock_external_api` — local mock inference endpoint used by the worker.

Worker behavior
- Bounded concurrency using `asyncio.Semaphore` (default concurrency configurable in `app/worker.py`).
- Exponential retry/backoff for 429 responses (`call_with_retries`).
- SQLite updates are performed via `asyncio.to_thread` to avoid blocking the event loop.

Quickstart
1. Create and activate a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
.venv/bin/pip install -r requirements.txt
```

2. Start the server (from project root):

```bash
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

3. Submit a batch and poll status (examples):

```bash
curl -s -X POST http://127.0.0.1:8000/batch -H "Content-Type: application/json" -d '["hello","world"]'
curl -s http://127.0.0.1:8000/batch/<batch_id>/status
curl -s http://127.0.0.1:8000/batch/<batch_id>/results
```

Architecture Flow Diagram
- The diagram below maps the main flow: the FastAPI endpoint schedules the background
  worker pool (asyncio tasks) which uses a Semaphore to bound concurrent external calls.
  Each worker call uses `call_with_retries` to implement retry/backoff on 429 responses
  and the worker writes progress and results to SQLite (`data/db.sqlite3`) via `app/db.py`.

![Architecture Flow Diagram](docs/diagram.svg)

End-to-end helper
- During development a small helper script was used at `/tmp/e2e_db2.sh` that demonstrates
  posting a batch, polling `/batch/{id}/status` until all prompts complete, and printing
  `/batch/{id}/results`.

Testing
- Unit tests: run `.venv/bin/python -m pytest -q`.
- Suggested next step: add an integration test that starts the app and validates the DB-backed
  lifecycle of a batch (submit → poll status → fetch results).

Notes
- The service now uses SQLite as the single source of truth for progress and results.
- If you previously used JSON files (data/results_*.json), consider migrating them to the DB
  for atomic updates and simpler queries.

CI
- See `.github/workflows/ci.yml` for the CI configuration (runs unit tests).

Contributing
- If you want me to add an automated integration test or commit the E2E script into the
  repository, say the word and I will add it.
