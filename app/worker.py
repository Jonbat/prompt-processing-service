import asyncio
import json
import time
import logging
from typing import Any, Callable, Dict, List

# This worker always calls the local mock external API implementation
# (`mock_external_api` in `app.main`). We keep the call in-process for
# development simplicity.

RESULT_DIR = "/workspaces/ai-batch-service/data"


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
    # Ensure result dir
    import os

    os.makedirs(RESULT_DIR, exist_ok=True)

    logging.getLogger("uvicorn.error").info(f"process_batch starting: {batch_id} prompts={len(prompts) if prompts else 0}")

    # write a quick marker file so we can detect that the background task started
    try:
        with open(os.path.join(RESULT_DIR, f"processing_{batch_id}.txt"), "w") as mf:
            mf.write(f"started prompts={len(prompts) if prompts else 0}\n")
    except Exception:
        pass

    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(prompt_text: str):
        async with semaphore:
            prompt = {"text": prompt_text}
            resp = await call_with_retries(_call_external, prompt)
            status = getattr(resp, "status_code", None)
            if status is None or status == 200:
                # resp is a dict-like success
                results.append({"prompt": prompt_text, "result": resp})
                logging.getLogger("uvicorn.error").info(f"processed prompt: {prompt_text} -> {resp}")
                try:
                    with open(os.path.join(RESULT_DIR, f"log_{batch_id}.txt"), "a") as lf:
                        lf.write(f"OK: {prompt_text} -> {resp}\n")
                except Exception:
                    pass
            else:
                results.append({"prompt": prompt_text, "error": f"status {status}"})
                logging.getLogger("uvicorn.error").info(f"processed prompt error: {prompt_text} -> {status}")

    tasks = [asyncio.create_task(worker(p)) for p in prompts]
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logging.getLogger("uvicorn.error").exception(f"process_batch worker tasks error: {e}")

    out_path = f"{RESULT_DIR}/results_{batch_id}.json"
    try:
        with open(out_path, "w") as f:
            json.dump({"batch_id": batch_id, "results": results}, f)
        logging.getLogger("uvicorn.error").info(f"process_batch finished: {batch_id} -> {out_path}")
    except Exception as e:
        logging.getLogger("uvicorn.error").exception(f"process_batch error writing results: {e}")
