import asyncio
import json
import time
import logging
from typing import Any, Callable, Dict, List

# This worker always calls the local mock external API implementation
# (`mock_external_api` in `app.main`). We keep the call in-process for
# development simplicity.

from app import db


async def _call_external(prompt: Dict[str, Any]):
    # Call the in-process mock external API implementation. This keeps the
    # demo self-contained and avoids HTTP loopback complexity during dev.
        from app.main import mock_external_api

        return await mock_external_api(prompt)


async def call_with_retries(callable_fn: Callable[..., Any], *args, max_retries: int = 5, base_backoff: float = 0.1, **kwargs):
    attempt = 0
    while True:
        resp = await callable_fn(*args, **kwargs)
        status = getattr(resp, "status_code", None)
        if status is None:
            # assume success-like return
            return resp

        if status == 429 and attempt < max_retries:
            backoff = base_backoff * (2 ** attempt)
            await asyncio.sleep(backoff)
            attempt += 1
            continue
        return resp


async def process_batch(batch_id: str, prompts: List[str], concurrency: int = 10):
    logging.getLogger("uvicorn.error").info(f"process_batch starting: {batch_id} prompts={len(prompts) if prompts else 0}")

    results = []
    semaphore = asyncio.Semaphore(concurrency)
    total = len(prompts) if prompts else 0
    completed = 0

    # Initialize DB job rows if DB adapter is present
    # create DB job rows (will raise if DB unavailable)
    try:
        ids = await asyncio.to_thread(db.create_job, batch_id, prompts)
    except Exception:
        ids = [None] * total

    async def worker(prompt_text: str):
        async with semaphore:
            prompt = {"text": prompt_text}
            resp = await call_with_retries(_call_external, prompt)
            status = getattr(resp, "status_code", None)
            if status is None or status == 200:
                # resp is a dict-like success
                results.append({"prompt": prompt_text, "result": resp})
                logging.getLogger("uvicorn.error").info(f"processed prompt: {prompt_text} -> {resp}")
            else:
                results.append({"prompt": prompt_text, "error": f"status {status}"})
                logging.getLogger("uvicorn.error").info(f"processed prompt error: {prompt_text} -> {status}")

            # update progress counter
            nonlocal completed
            completed += 1
            # persist/update to sqlite
            try:
                idx = len(results) - 1
                pid = ids[idx] if ids and idx is not None and idx < len(ids) else None
                if status is None or status == 200:
                    st = "done"
                    res_obj = resp
                else:
                    st = "error"
                    res_obj = {"error": f"status {status}"}
                if pid is not None:
                    await asyncio.to_thread(db.update_prompt_result, pid, st, res_obj)
            except Exception:
                logging.getLogger("uvicorn.error").exception("failed to update db for prompt")

    tasks = [asyncio.create_task(worker(p)) for p in prompts]
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logging.getLogger("uvicorn.error").exception(f"process_batch worker tasks error: {e}")

    logging.getLogger("uvicorn.error").info(f"process_batch finished: {batch_id} (db-backed)")
