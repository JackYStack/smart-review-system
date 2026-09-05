from __future__ import annotations

import logging
import os
import socket
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.scheme_review_task import ReviewTaskStatus, SchemeReviewTask
from app.models.worker_heartbeat import WorkerHeartbeat
from app.services.review_pipeline import run_review_pipeline
from app.services.review_settings import (
    MAX_PARALLELISM,
    get_review_timeout_seconds,
    get_worker_parallel_tasks,
)

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL_SECONDS = 10.0


def _write_heartbeat(db: Session, worker_id: str, active_tasks: int, status: str = "running") -> None:
    row = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_id == worker_id).first()
    now = datetime.now(UTC)
    if row is None:
        row = WorkerHeartbeat(
            worker_id=worker_id,
            status=status,
            active_tasks=active_tasks,
            started_at=now,
            last_seen_at=now,
        )
        db.add(row)
    else:
        row.status = status
        row.active_tasks = active_tasks
        row.last_seen_at = now
    db.commit()


def _append_runtime_log(task: SchemeReviewTask, level: str, message: str) -> None:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    task.review_log = (task.review_log or "") + f"[{ts}] {level.upper()} {message}\n"


def _renew_task_leases(
    db: Session,
    worker_id: str,
    task_ids: list[int],
    *,
    lease_seconds: int,
) -> int:
    """Keep leases alive while the worker's futures are still running.

    A single review can contain several sequential OCR/LLM calls.  Giving the
    task one lease only when it is claimed can therefore expire even while the
    worker is healthy, allowing another task to mark the live review stale.
    """

    if not task_ids:
        return 0
    expires_at = datetime.now(UTC) + timedelta(seconds=max(1200, lease_seconds))
    return int(
        db.query(SchemeReviewTask)
        .filter(
            SchemeReviewTask.id.in_(task_ids),
            SchemeReviewTask.status == ReviewTaskStatus.processing,
            SchemeReviewTask.lease_owner == worker_id,
        )
        .update(
            {SchemeReviewTask.lease_expires_at: expires_at},
            synchronize_session=False,
        )
        or 0
    )


def _claim_next_pending_task_id(db: Session, worker_id: str) -> int | None:
    stmt: Select[tuple[SchemeReviewTask]] = (
        select(SchemeReviewTask)
        .where(SchemeReviewTask.status == ReviewTaskStatus.pending)
        .order_by(SchemeReviewTask.priority.desc(), SchemeReviewTask.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        db.rollback()
        return None
    row.status = ReviewTaskStatus.processing
    now = datetime.now(UTC)
    lease_seconds = max(1200, int(get_review_timeout_seconds(db)) + 600)
    row.lease_owner = worker_id
    row.lease_expires_at = now + timedelta(seconds=lease_seconds)
    _append_runtime_log(row, "info", "任务已被 worker 领取，等待执行")
    db.commit()
    return int(row.id)


def process_scheme_review_task(task_id: int) -> None:
    run_review_pipeline(task_id)


def run_worker_forever(
    *,
    poll_interval_seconds: float = 2.0,
) -> None:
    logger.info(
        "Review worker started (poll_interval=%.1fs)",
        poll_interval_seconds,
    )
    pool = ThreadPoolExecutor(max_workers=MAX_PARALLELISM)
    inflight: dict[Future, int] = {}
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    last_heartbeat = 0.0
    try:
        while True:
            # Reap completed tasks
            done_ids = [f for f in list(inflight) if f.done()]
            for fut in done_ids:
                tid = inflight.pop(fut)
                try:
                    fut.result()
                except Exception:
                    logger.exception("Unexpected worker error while processing task #%d", tid)

            try:
                with SessionLocal() as db:
                    limit = get_worker_parallel_tasks(db)
                    now_monotonic = time.monotonic()
                    if now_monotonic - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                        lease_seconds = max(
                            1200, int(get_review_timeout_seconds(db)) + 600
                        )
                        _renew_task_leases(
                            db,
                            worker_id,
                            list(inflight.values()),
                            lease_seconds=lease_seconds,
                        )
                        _write_heartbeat(db, worker_id, len(inflight))
                        last_heartbeat = now_monotonic
            except Exception:
                logger.exception("Failed to read worker_parallel_tasks; defaulting to 1")
                limit = 1

            while len(inflight) < limit:
                try:
                    with SessionLocal() as db:
                        task_id = _claim_next_pending_task_id(db, worker_id)
                except OperationalError:
                    logger.exception("Failed to claim pending task due to database error")
                    break
                except Exception:
                    logger.exception("Failed to claim pending task")
                    break

                if task_id is None:
                    break

                logger.info("Start processing task #%d", task_id)

                def _run(tid: int) -> None:
                    process_scheme_review_task(tid)

                fut = pool.submit(_run, task_id)
                inflight[fut] = task_id

            if not inflight:
                time.sleep(max(0.5, poll_interval_seconds))
            else:
                wait(inflight.keys(), timeout=max(0.5, poll_interval_seconds), return_when=FIRST_COMPLETED)
    finally:
        try:
            with SessionLocal() as db:
                _write_heartbeat(db, worker_id, len(inflight), status="stopped")
        except Exception:
            logger.exception("Failed to write worker shutdown heartbeat")
        pool.shutdown(wait=True)
