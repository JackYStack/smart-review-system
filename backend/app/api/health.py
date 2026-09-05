from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services import minio_storage


router = APIRouter(prefix="/health", tags=["health"])


class DependencyHealth(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: int
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    checked_at: datetime
    dependencies: dict[str, DependencyHealth]


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def _check_database(db: Session) -> DependencyHealth:
    started_at = perf_counter()
    try:
        db.execute(text("SELECT 1"))
        return DependencyHealth(
            status="ok",
            latency_ms=_elapsed_ms(started_at),
            detail="database connection is available",
        )
    except Exception as exc:
        # Readiness is public, so report the exception type without exposing DSNs or credentials.
        return DependencyHealth(
            status="error",
            latency_ms=_elapsed_ms(started_at),
            detail=f"database connection failed ({type(exc).__name__})",
        )


def _check_minio() -> DependencyHealth:
    started_at = perf_counter()
    try:
        settings = get_settings()
        client = minio_storage.get_client(timeout_seconds=3)
        if not client.bucket_exists(settings.minio_bucket):
            return DependencyHealth(
                status="error",
                latency_ms=_elapsed_ms(started_at),
                detail="configured object-storage bucket does not exist",
            )
        return DependencyHealth(
            status="ok",
            latency_ms=_elapsed_ms(started_at),
            detail="object storage and configured bucket are available",
        )
    except Exception as exc:
        return DependencyHealth(
            status="error",
            latency_ms=_elapsed_ms(started_at),
            detail=f"object storage connection failed ({type(exc).__name__})",
        )


@router.get("/live", response_model=HealthResponse)
def live() -> HealthResponse:
    """Process liveness only; this endpoint never waits for external dependencies."""

    return HealthResponse(
        status="ok",
        checked_at=datetime.now(UTC),
        dependencies={},
    )


@router.get("/ready", response_model=HealthResponse)
def ready(db: Session = Depends(get_db)) -> HealthResponse | JSONResponse:
    """Dependency readiness for load balancers and deployment verification."""

    dependencies = {
        "database": _check_database(db),
        "object_storage": _check_minio(),
    }
    is_ready = all(item.status == "ok" for item in dependencies.values())
    payload = HealthResponse(
        status="ok" if is_ready else "not_ready",
        checked_at=datetime.now(UTC),
        dependencies=dependencies,
    )
    if is_ready:
        return payload
    return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))
