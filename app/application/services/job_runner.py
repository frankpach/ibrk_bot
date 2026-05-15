# app/application/services/job_runner.py
"""Background job runner using ThreadPoolExecutor.

Jobs are persisted in SQLite `background_jobs` table.
"""
from __future__ import annotations

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from datetime import datetime, timezone
from typing import Any, Callable

from app.infrastructure.db.compat import get_connection

logger = logging.getLogger(__name__)

PENDING = "pending"
RUNNING = "running"
SUCCESS = "success"
FAILED = "failed"

_global_runner: BackgroundJobRunner | None = None


def get_global_runner() -> BackgroundJobRunner:
    global _global_runner
    if _global_runner is None:
        _global_runner = BackgroundJobRunner(max_workers=3)
    return _global_runner


def set_global_runner(runner: BackgroundJobRunner | None) -> None:
    global _global_runner
    _global_runner = runner


class BackgroundJobRunner:
    """Runs background jobs in a ThreadPoolExecutor.

    - max_workers=3 (configurable)
    - Timeout per job enforced via concurrent.futures.wait
    - Jobs never deleted, only status changed
    """

    def __init__(self, max_workers: int = 3):
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bgjob")
        self._ensure_table()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(
        self,
        job_type: str,
        fn: Callable,
        timeout_seconds: int = 60,
        **params: Any,
    ) -> str:
        """Submit a job and return its ID immediately (<100ms)."""
        job_id = str(uuid.uuid4())
        self._save_job(job_id, job_type, PENDING, params)
        self._pool.submit(self._run, job_id, fn, params, timeout_seconds)
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute(
                """SELECT job_id, job_type, status, params, result, error,
                          created_at, started_at, completed_at
                   FROM background_jobs WHERE job_id=?""",
                (job_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "job_id": row["job_id"],
                "job_type": row["job_type"],
                "status": row["status"],
                "params": json.loads(row["params"] or "{}"),
                "result": json.loads(row["result"] or "null") if row["result"] else None,
                "error": row["error"],
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
            }
        finally:
            conn.close()

    def list_jobs(
        self,
        job_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        conn = get_connection()
        try:
            sql = """SELECT job_id, job_type, status, params, result, error,
                            created_at, started_at, completed_at
                     FROM background_jobs WHERE 1=1"""
            args: list[Any] = []
            if job_type:
                sql += " AND job_type=?"
                args.append(job_type)
            if status:
                sql += " AND status=?"
                args.append(status)
            sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            args.extend([limit, offset])
            rows = conn.execute(sql, args).fetchall()
            out = []
            for r in rows:
                out.append({
                    "job_id": r["job_id"],
                    "job_type": r["job_type"],
                    "status": r["status"],
                    "params": json.loads(r["params"] or "{}"),
                    "result": json.loads(r["result"] or "null") if r["result"] else None,
                    "error": r["error"],
                    "created_at": r["created_at"],
                    "started_at": r["started_at"],
                    "completed_at": r["completed_at"],
                })
            return out
        finally:
            conn.close()

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, job_id: str, fn: Callable, params: dict, timeout_seconds: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._update_status(job_id, RUNNING, started_at=now)
        future = self._pool.submit(fn, **params)
        done, not_done = futures_wait([future], timeout=timeout_seconds)
        now = datetime.now(timezone.utc).isoformat()
        if not done:
            future.cancel()
            self._update_status(job_id, FAILED, error="timeout", completed_at=now)
            logger.warning(f"Job {job_id} timed out after {timeout_seconds}s")
            return
        try:
            result = future.result()
            self._update_status(
                job_id, SUCCESS,
                result=json.dumps(result, default=str),
                completed_at=now,
            )
        except Exception as exc:
            self._update_status(job_id, FAILED, error=str(exc), completed_at=now)
            logger.exception(f"Job {job_id} failed")

    def _ensure_table(self) -> None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='background_jobs'"
            ).fetchone()
            if row:
                return
            conn.execute("""
                CREATE TABLE IF NOT EXISTS background_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    params TEXT,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bgjobs_type ON background_jobs(job_type, status, created_at)")
            conn.commit()
        finally:
            conn.close()

    def _save_job(self, job_id: str, job_type: str, status: str, params: dict) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO background_jobs
                   (job_id, job_type, status, params, created_at)
                   VALUES (?,?,?,?,?)""",
                (job_id, job_type, status, json.dumps(params, default=str),
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def _update_status(
        self,
        job_id: str,
        status: str,
        result: str | None = None,
        error: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> None:
        conn = get_connection()
        try:
            parts = ["status=?"]
            args: list[Any] = [status]
            if result is not None:
                parts.append("result=?")
                args.append(result)
            if error is not None:
                parts.append("error=?")
                args.append(error)
            if started_at is not None:
                parts.append("started_at=?")
                args.append(started_at)
            if completed_at is not None:
                parts.append("completed_at=?")
                args.append(completed_at)
            args.append(job_id)
            sql = f"UPDATE background_jobs SET {', '.join(parts)} WHERE job_id=?"
            conn.execute(sql, args)
            conn.commit()
        finally:
            conn.close()
