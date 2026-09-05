from __future__ import annotations

import subprocess
import json
from datetime import UTC, datetime, timedelta
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
from app.models.user import User
from app.models.configuration_audit import ConfigurationAudit
from app.models.worker_heartbeat import WorkerHeartbeat
from app.schemas.configuration_audit import (
    ConfigurationAuditPublic,
    ConfigurationHistoryPublic,
)
from app.schemas.integration_settings import (
    DocumentIntegrationPublic,
    IntegrationSettingsPublic,
    IntegrationSettingsUpdate,
    IntegrationTestRequest,
    IntegrationTestResult,
    ServiceStatusItem,
    ServiceStatusPublic,
    WorkflowIntegrationPublic,
)
from app.services import minio_storage
from app.services.integration_settings import (
    get_or_create_integration_settings,
    resolve_document_integration,
    resolve_workflow_integration,
)
from app.services.onlyoffice_settings import get_effective_onlyoffice, jwt_configured
from app.services.secret_store import encrypt_secret
from app.services.configuration_audit import (
    apply_integration_snapshot,
    integration_snapshot,
    record_integration_audit,
)
from app.services.dify_settings import get_dify_url_and_key
from app.services.dify_client import list_dataset_catalog
from app.services.llm.resolve import build_model_provider_public

router = APIRouter(prefix="/settings", tags=["settings"])


def _public(db: Session) -> IntegrationSettingsPublic:
    workflow = resolve_workflow_integration(db)
    document = resolve_document_integration(db)
    return IntegrationSettingsPublic(
        workflow=WorkflowIntegrationPublic(
            enabled=workflow.enabled,
            base_url=workflow.base_url,
            api_key_configured=bool(workflow.api_key),
            user_prefix=workflow.user_prefix,
            timeout_seconds=workflow.timeout_seconds,
            output_variable=workflow.output_variable,
            output_format=workflow.output_format,  # type: ignore[arg-type]
            accept_partial=workflow.accept_partial,
            continue_on_failure=workflow.continue_on_failure,
            source=workflow.source,  # type: ignore[arg-type]
        ),
        document=DocumentIntegrationPublic(
            paddleocr_api_url=document.paddleocr_api_url,
            paddleocr_api_key_configured=bool(document.paddleocr_api_key),
            paddleocr_timeout_seconds=document.paddleocr_timeout_seconds,
            convert_timeout_seconds=document.convert_timeout_seconds,
            libreoffice_configured=bool(document.libreoffice_bin),
            source=document.source,  # type: ignore[arg-type]
        ),
    )


@router.get("/integrations", response_model=IntegrationSettingsPublic)
def get_integrations(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> IntegrationSettingsPublic:
    return _public(db)


@router.put("/integrations", response_model=IntegrationSettingsPublic)
def update_integrations(
    body: IntegrationSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> IntegrationSettingsPublic:
    row = get_or_create_integration_settings(db)
    before = integration_snapshot(row)
    row.dify_workflow_enabled = body.dify_workflow_enabled
    row.dify_workflow_base_url = body.dify_workflow_base_url.rstrip("/")
    row.dify_workflow_user_prefix = body.dify_workflow_user_prefix or "smart-review"
    row.dify_workflow_timeout_seconds = body.dify_workflow_timeout_seconds
    row.dify_workflow_output_variable = body.dify_workflow_output_variable
    row.dify_workflow_output_format = body.dify_workflow_output_format
    row.dify_workflow_accept_partial = body.dify_workflow_accept_partial
    row.dify_workflow_continue_on_failure = body.dify_workflow_continue_on_failure
    if body.dify_workflow_api_key is not None and body.dify_workflow_api_key.strip():
        row.dify_workflow_api_key = encrypt_secret(body.dify_workflow_api_key)
    row.paddleocr_api_url = body.paddleocr_api_url
    row.paddleocr_timeout_seconds = body.paddleocr_timeout_seconds
    row.paddle_convert_timeout_seconds = body.paddle_convert_timeout_seconds
    if body.paddleocr_api_key is not None and body.paddleocr_api_key.strip():
        row.paddleocr_api_key = encrypt_secret(body.paddleocr_api_key)
    after = integration_snapshot(row)
    if before != after:
        record_integration_audit(
            db,
            user=user,
            action="update",
            before=before,
            after=after,
        )
    db.commit()
    return _public(db)


def _audit_public(row: ConfigurationAudit) -> ConfigurationAuditPublic:
    try:
        fields = json.loads(row.changed_fields_json or "[]")
    except json.JSONDecodeError:
        fields = []
    return ConfigurationAuditPublic(
        id=row.id,
        section=row.section,
        action=row.action,
        actor_username=row.actor_username,
        changed_fields=[str(item) for item in fields if isinstance(item, str)],
        created_at=row.created_at,
        can_rollback=bool(row.rollback_snapshot_json),
    )


@router.get("/integrations/history", response_model=ConfigurationHistoryPublic)
def get_integration_history(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ConfigurationHistoryPublic:
    rows = (
        db.query(ConfigurationAudit)
        .filter(ConfigurationAudit.section == "integrations")
        .order_by(ConfigurationAudit.id.desc())
        .limit(50)
        .all()
    )
    return ConfigurationHistoryPublic(items=[_audit_public(row) for row in rows])


@router.post(
    "/integrations/history/{audit_id}/rollback",
    response_model=IntegrationSettingsPublic,
)
def rollback_integration_settings(
    audit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> IntegrationSettingsPublic:
    audit = db.get(ConfigurationAudit, audit_id)
    if audit is None or audit.section != "integrations":
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="配置历史不存在")
    try:
        target = json.loads(audit.rollback_snapshot_json)
    except (json.JSONDecodeError, TypeError) as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="历史快照不可用") from exc
    row = get_or_create_integration_settings(db)
    before = integration_snapshot(row)
    apply_integration_snapshot(row, target)
    after = integration_snapshot(row)
    record_integration_audit(
        db,
        user=user,
        action=f"rollback:{audit_id}",
        before=before,
        after=after,
    )
    db.commit()
    return _public(db)


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("服务地址必须是完整的 http:// 或 https:// 地址")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


@router.post("/integrations/test", response_model=IntegrationTestResult)
def test_integration(
    body: IntegrationTestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> IntegrationTestResult:
    started = perf_counter()
    try:
        if body.service == "dify_workflow":
            cfg = resolve_workflow_integration(db)
            if not cfg.base_url or not cfg.api_key:
                raise ValueError("尚未配置 Workflow API 地址或应用密钥")
            response = httpx.get(
                f"{cfg.base_url.rstrip('/')}/info",
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                timeout=15,
            )
            if response.is_error:
                try:
                    detail = str((response.json() or {}).get("message") or response.text)
                except ValueError:
                    detail = response.text
                raise ValueError(f"Dify 返回 HTTP {response.status_code}: {detail[:300]}")
            data = response.json()
            app_name = str(data.get("name") or data.get("app_name") or "").strip() or None
            detail = f"API 服务可用{f'，应用：{app_name}' if app_name else ''}"
            return IntegrationTestResult(
                service=body.service,
                ok=True,
                status="connected",
                detail=detail,
                latency_ms=int((perf_counter() - started) * 1000),
                app_name=app_name,
            )
        if body.service == "dify_dataset":
            base_url, api_key = get_dify_url_and_key(db)
            rows = list_dataset_catalog(base_url, api_key)
            detail = f"Dataset API 可用，发现 {len(rows)} 个知识库"
            return IntegrationTestResult(
                service=body.service,
                ok=True,
                status="connected",
                detail=detail,
                latency_ms=int((perf_counter() - started) * 1000),
            )
        if body.service == "paddleocr":
            cfg = resolve_document_integration(db)
            headers = {}
            if cfg.paddleocr_api_key:
                headers["Authorization"] = f"Bearer {cfg.paddleocr_api_key}"
            response = httpx.get(
                f"{_origin(cfg.paddleocr_api_url)}/openapi.json",
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            paths = (response.json() or {}).get("paths") or {}
            if "/layout-parsing" not in paths:
                raise ValueError("服务可访问，但未发现 /layout-parsing 接口")
            detail = "PaddleOCR PP-StructureV3 接口可用"
        elif body.service == "libreoffice":
            cfg = resolve_document_integration(db)
            if not cfg.libreoffice_bin:
                raise ValueError("未找到 LibreOffice/soffice 可执行程序")
            process = subprocess.run(
                [cfg.libreoffice_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if process.returncode != 0:
                raise ValueError((process.stderr or process.stdout or "版本检测失败")[:300])
            detail = (process.stdout or process.stderr or "LibreOffice 可用").strip()[:300]
        elif body.service == "onlyoffice":
            cfg = get_effective_onlyoffice(db)
            if not cfg.docs_url or not jwt_configured(cfg):
                raise ValueError("OnlyOffice 地址或 JWT 尚未配置")
            response = httpx.get(f"{cfg.docs_url.rstrip('/')}/healthcheck", timeout=15)
            response.raise_for_status()
            detail = f"Document Server 可用：{response.text.strip()[:100]}"
        else:
            settings = get_settings()
            client = minio_storage.get_client(timeout_seconds=10)
            exists = client.bucket_exists(settings.minio_bucket)
            detail = f"MinIO 可用，Bucket {settings.minio_bucket} {'已存在' if exists else '尚未创建'}"
        return IntegrationTestResult(
            service=body.service,
            ok=True,
            status="connected",
            detail=detail,
            latency_ms=int((perf_counter() - started) * 1000),
        )
    except Exception as exc:
        return IntegrationTestResult(
            service=body.service,
            ok=False,
            status="error",
            detail=str(exc)[:500],
            latency_ms=int((perf_counter() - started) * 1000),
        )


@router.get("/services/status", response_model=ServiceStatusPublic)
def get_service_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ServiceStatusPublic:
    workflow = resolve_workflow_integration(db)
    document = resolve_document_integration(db)
    onlyoffice = get_effective_onlyoffice(db)
    settings = get_settings()
    rows = [
        ServiceStatusItem(
            service="dify_workflow",
            label="Dify Workflow",
            state="configured" if workflow.base_url and workflow.api_key else "unconfigured",
            detail=("已启用" if workflow.enabled else "已停用") + f" · {workflow.source}",
            editable=True,
        ),
        ServiceStatusItem(
            service="dify_dataset",
            label="Dify知识库",
            state=(
                "configured"
                if all(get_dify_url_and_key(db))
                else "unconfigured"
            ),
            detail="Dataset API用于法规规范检索",
            editable=True,
        ),
        ServiceStatusItem(
            service="llm",
            label="大模型",
            state=(
                "configured"
                if build_model_provider_public(db).default_provider
                else "unconfigured"
            ),
            detail=(
                f"默认供应商：{build_model_provider_public(db).default_provider}"
                if build_model_provider_public(db).default_provider
                else "尚未选择默认供应商"
            ),
            editable=True,
        ),
        ServiceStatusItem(
            service="paddleocr",
            label="PaddleOCR",
            state="configured" if document.paddleocr_api_url else "unconfigured",
            detail=document.paddleocr_api_url or "未配置服务地址",
            editable=True,
        ),
        ServiceStatusItem(
            service="libreoffice",
            label="LibreOffice",
            state="configured" if document.libreoffice_bin else "unconfigured",
            detail="已检测到可执行程序" if document.libreoffice_bin else "未检测到可执行程序",
            editable=False,
        ),
        ServiceStatusItem(
            service="onlyoffice",
            label="OnlyOffice",
            state="configured" if onlyoffice.docs_url and jwt_configured(onlyoffice) else "unconfigured",
            detail=onlyoffice.docs_url or "未配置 Document Server",
            editable=True,
        ),
        ServiceStatusItem(
            service="minio",
            label="MinIO",
            state="configured",
            detail=f"{settings.minio_endpoint} / {settings.minio_bucket}（部署配置）",
            editable=False,
        ),
    ]
    try:
        db.execute(text("SELECT 1"))
        db_state, db_detail = "connected", "数据库连接正常（部署配置）"
    except Exception as exc:
        db_state, db_detail = "error", str(exc)[:200]
    rows.append(
        ServiceStatusItem(
            service="mysql",
            label="MySQL",
            state=db_state,  # type: ignore[arg-type]
            detail=db_detail,
            editable=False,
        )
    )
    heartbeat = (
        db.query(WorkerHeartbeat)
        .order_by(WorkerHeartbeat.last_seen_at.desc())
        .first()
    )
    if heartbeat is None:
        worker_state, worker_detail = "unconfigured", "尚未收到Worker心跳"
    else:
        last_seen = heartbeat.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)
        online = datetime.now(UTC) - last_seen <= timedelta(seconds=35)
        worker_state = "connected" if online and heartbeat.status == "running" else "error"
        worker_detail = (
            f"在线 · 活动任务 {heartbeat.active_tasks} · 最后心跳 {last_seen.isoformat()}"
            if worker_state == "connected"
            else f"心跳已过期 · {last_seen.isoformat()}"
        )
    rows.append(
        ServiceStatusItem(
            service="worker",
            label="审核Worker",
            state=worker_state,  # type: ignore[arg-type]
            detail=worker_detail,
            editable=False,
        )
    )
    return ServiceStatusPublic(services=rows)
