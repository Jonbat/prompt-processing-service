import sqlite3
import os
import time
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "db.sqlite3")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            prompt TEXT NOT NULL,
            status TEXT NOT NULL,
            result TEXT,
            created_at REAL,
            updated_at REAL
        );
        """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_batch ON prompts(batch_id);")
        conn.commit()
    finally:
        conn.close()


def create_job(batch_id: str, prompts: list) -> list:
    """Insert prompt rows and return their ids in order."""
    now = time.time()
    conn = _conn()
    try:
        cur = conn.cursor()
        ids = []
        for p in prompts:
            cur.execute(
                "INSERT INTO prompts(batch_id,prompt,status,created_at,updated_at) VALUES (?,?,?,?,?)",
                (batch_id, p, "pending", now, now),
            )
            ids.append(cur.lastrowid)
        conn.commit()
        return ids
    finally:
        conn.close()


def update_prompt_result(prompt_id: int, status: str, result: dict | None):
    now = time.time()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prompts SET status=?, result=?, updated_at=? WHERE id=?",
            (status, json.dumps(result) if result is not None else None, now, prompt_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_progress(batch_id: str) -> dict:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM prompts WHERE batch_id=?", (batch_id,))
        total = cur.fetchone()["total"]
        cur.execute(
            "SELECT COUNT(*) as completed FROM prompts WHERE batch_id=? AND status='done'",
            (batch_id,),
        )
        completed = cur.fetchone()["completed"]
        return {"batch_id": batch_id, "total": total, "completed": completed}
    finally:
        conn.close()


def get_results(batch_id: str) -> dict:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT prompt, result, status FROM prompts WHERE batch_id=? ORDER BY id ASC",
            (batch_id,),
        )
        rows = cur.fetchall()
        results = []
        for r in rows:
            res = None
            if r["result"]:
                try:
                    res = json.loads(r["result"])
                except Exception:
                    res = r["result"]
            results.append({"prompt": r["prompt"], "status": r["status"], "result": res})
        return {"batch_id": batch_id, "results": results}
    finally:
        conn.close()
