import asyncio
import json
import random
import uuid
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, File, UploadFile, HTTPException, Body
from fastapi.responses import JSONResponse

from .worker import process_batch
from . import db
import os
import json


# initialize sqlite DB
try:
    db.init_db()
except Exception:
    pass

app = FastAPI(title="AI Batch Service")


@app.post("/batch")
async def submit_batch(background: BackgroundTasks, prompts: Optional[List[str]] = Body(None)):
    # Accept a raw JSON array in the request body.
    if prompts is None:
        raise HTTPException(status_code=400, detail="Provide prompts JSON array in the request body")

    batch_id = str(uuid.uuid4())
    background.add_task(process_batch, batch_id, prompts)

    return JSONResponse({"batch_id": batch_id, "status": "accepted"}, status_code=202)


@app.post("/batch/upload")
async def upload_batch(background: BackgroundTasks, file: UploadFile = File(...)):
    # Accept a file upload (multipart/form-data) containing a JSON array
    content = await file.read()
    try:
        prompts = json.loads(content.decode())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")

    batch_id = str(uuid.uuid4())
    background.add_task(process_batch, batch_id, prompts)
    return JSONResponse({"batch_id": batch_id, "status": "accepted"}, status_code=202)


@app.get("/batch/{batch_id}/results")
async def get_results(batch_id: str):
    try:
        data = db.get_results(batch_id)
        # return 404 if no rows exist for this batch
        if not data or not data.get("results"):
            raise HTTPException(status_code=404, detail="Results not ready")
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read results from DB")


@app.get("/batch/{batch_id}/status")
async def get_status(batch_id: str):
    try:
        prog = db.get_progress(batch_id)
        if not prog:
            raise HTTPException(status_code=404, detail="Batch not found or not started yet")
        return prog
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read progress from DB")


@app.post("/mock_external_api")
async def mock_external_api(prompt: dict):
    # Simulate a rate-limited external API: sometimes return 429
    # On success, return a fake inference result
    if random.random() < 0.25:
        return JSONResponse({"detail": "rate limited"}, status_code=429)

    # simulate some processing latency
    await asyncio.sleep(0.01)
    return {"input": prompt, "output": f"echo: {prompt.get('text', '')[:50]}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
