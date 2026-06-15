# AI Batch Service (minimal)

Summary
- A small FastAPI service that accepts a batch of prompts, processes them concurrently against a mock rate-limited inference endpoint, and aggregates results to JSON files.

Quickstart
- Create a virtualenv and install: `pip install -r requirements.txt`
- Run the app: `uvicorn app.main:app --reload --port 8000`
- Submit a batch (example using `curl`):

```bash
curl -X POST "http://127.0.0.1:8000/batch" -H "Content-Type: application/json" -d '["hello","world"]'
```

Design
- Concurrency: Uses `asyncio.Semaphore` to bound concurrent outbound requests (default `concurrency=10` in `process_batch`). Workers are created as tasks but concurrency enforced by the semaphore to avoid unbounded concurrency.
- Retry / Backoff: `call_with_retries` implements basic exponential backoff for HTTP 429 responses (configurable `max_retries` and `base_backoff`).
- Aggregation: Results are saved to `data/results_{batch_id}.json` once the batch completes.

Architecture Diagram
- Visual architecture is available below and in `docs/diagram.svg`.

![Architecture diagram](docs/diagram.svg)

Testing
- Unit tests use `pytest` and `pytest-asyncio`. The retry behavior is tested in `tests/test_retry.py` by simulating 429 responses with a mock call.

CI
- Basic GitHub Actions workflow at `.github/workflows/ci.yml` runs tests on push/pull requests.

Next steps you might want
- Add persistent DB (SQLite/Postgres) instead of JSON files.
- Add status tracking endpoint to report progress of a running batch.
- Add instrumentation and graceful shutdown handling for background tasks.
