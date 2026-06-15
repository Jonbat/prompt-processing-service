# AI Prompt Batch Processing Service

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

Local testing (end-to-end)
Follow these steps to run and test the service locally.

1. Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the unit tests:

```bash
.venv/bin/python -m pytest -q
```

3. Start the server (project root):

```bash
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

4. Submit a small batch (example):

```bash
curl -s -X POST "http://127.0.0.1:8000/batch" \
	-H "Content-Type: application/json" \
	-d '["prompt one","prompt two","prompt three"]' | jq
```

5. Poll job status (replace <batch_id> with returned id):

```bash
curl -s http://127.0.0.1:8000/batch/<batch_id>/status | jq
```

6. Retrieve results when complete:

```bash
curl -s http://127.0.0.1:8000/batch/<batch_id>/results | jq
```

7. Cleanup (optional):

```bash
rm -rf data/progress_<batch_id>.json data/results_<batch_id>.json data/log_<batch_id>.txt data/processing_<batch_id>.txt
```

Notes
- If `uvicorn` is not installed into your active environment, install it with `pip install uvicorn` inside the venv.
- The status endpoint reads `data/progress_<batch_id>.json` written by the worker; if that file is absent but `results_<batch_id>.json` exists the status endpoint will show completed counts.

CI
- Basic GitHub Actions workflow at `.github/workflows/ci.yml` runs tests on push/pull requests.