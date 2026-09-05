from __future__ import annotations

import json
import platform
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.settings_integrations import get_service_status
from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
from app.models.user import User
from app.schemas.diagnostics import DiagnosticReportPublic
from app.services.integration_settings import (
    resolve_document_integration,
    resolve_workflow_integration,
)
from app.services.review_settings import (
    get_compilation_basis_concurrency,
    get_content_concurrency,
    get_context_consistency_concurrency,
    get_review_prompt_debug_enabled,
    get_review_timeout_seconds,
    get_worker_parallel_tasks,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _build_report(db: Session, user: User) -> DiagnosticReportPublic:
    settings = get_settings()
    workflow = resolve_workflow_integration(db)
    document = resolve_document_integration(db)
    try:
        revision = str(db.execute(text("SELECT version_num FROM alembic_version")).scalar() or "")
    except Exception:
        revision = "unknown"
    services = get_service_status(db=db, _=user).services
    return DiagnosticReportPublic(
        generated_at=datetime.now(UTC),
        system={
            "api_title": "SmartReview API",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "database_revision": revision,
        },
        deployment={
            "mysql_host": settings.mysql_host,
            "mysql_port": settings.mysql_port,
            "mysql_database": settings.mysql_db,
            "minio_endpoint": settings.minio_endpoint,
            "minio_bucket": settings.minio_bucket,
            "minio_secure": settings.minio_secure,
            "secrets_included": False,
        },
        integrations={
            "workflow": {
                "enabled": workflow.enabled,
                "base_url": workflow.base_url,
                "api_key_configured": bool(workflow.api_key),
                "timeout_seconds": workflow.timeout_seconds,
                "output_variable": workflow.output_variable,
                "output_format": workflow.output_format,
                "source": workflow.source,
            },
            "document": {
                "paddleocr_api_url": document.paddleocr_api_url,
                "paddleocr_api_key_configured": bool(document.paddleocr_api_key),
                "paddleocr_timeout_seconds": document.paddleocr_timeout_seconds,
                "convert_timeout_seconds": document.convert_timeout_seconds,
                "libreoffice_configured": bool(document.libreoffice_bin),
                "source": document.source,
            },
        },
        review_runtime={
            "review_timeout_seconds": get_review_timeout_seconds(db),
            "prompt_debug_enabled": get_review_prompt_debug_enabled(db),
            "worker_parallel_tasks": get_worker_parallel_tasks(db),
            "compilation_basis_concurrency": get_compilation_basis_concurrency(db),
            "context_consistency_concurrency": get_context_consistency_concurrency(db),
            "content_concurrency": get_content_concurrency(db),
        },
        services=[item.model_dump(mode="json") for item in services],
    )


@router.get("/diagnostics", response_model=DiagnosticReportPublic)
def get_diagnostics(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> DiagnosticReportPublic:
    return _build_report(db, user)


@router.get("/diagnostics/download")
def download_diagnostics(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> Response:
    report = _build_report(db, user)
    content = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2).encode("utf-8")
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="smartreview-diagnostics-{stamp}.json"'},
    )

