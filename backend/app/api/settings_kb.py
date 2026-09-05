import httpx
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
from app.models.knowledge_base_settings import KnowledgeBaseSettings
from app.models.user import User
from app.schemas.knowledge_base import (
    DifyDatasetItem,
    KnowledgeBasePublic,
    KnowledgeBaseTestRequest,
    KnowledgeBaseTestResult,
    KnowledgeBaseUpdate,
)
from app.services.dify_client import list_dataset_catalog, retrieve_dataset_chunks
from app.services.dify_settings import get_dify_dataset_name_prefix, get_dify_url_and_key
from app.services.secret_store import encrypt_secret

router = APIRouter(prefix="/settings", tags=["settings"])


def _effective_config(db: Session) -> tuple[str, bool]:
    url, key_plain = get_dify_url_and_key(db)
    return url, bool(key_plain)


@router.get("/knowledge-base", response_model=KnowledgeBasePublic)
def get_knowledge_base_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> KnowledgeBasePublic:
    url, configured = _effective_config(db)
    return KnowledgeBasePublic(
        dify_base_url=url,
        dify_dataset_name_prefix=get_dify_dataset_name_prefix(db),
        api_key_configured=configured,
    )


@router.put("/knowledge-base", response_model=KnowledgeBasePublic)
def update_knowledge_base_settings(
    body: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> KnowledgeBasePublic:
    row = db.query(KnowledgeBaseSettings).order_by(KnowledgeBaseSettings.id).first()
    if row is None:
        row = KnowledgeBaseSettings(dify_base_url="", dify_api_key="", dify_dataset_name_prefix="")
        db.add(row)
        db.flush()

    row.dify_base_url = body.dify_base_url
    row.dify_dataset_name_prefix = body.dify_dataset_name_prefix
    if body.dify_api_key is not None and body.dify_api_key.strip():
        row.dify_api_key = encrypt_secret(body.dify_api_key)
    db.commit()
    db.refresh(row)

    settings = get_settings()
    url = (row.dify_base_url or "").strip() or (settings.dify_base_url or "").strip()
    key_db = (row.dify_api_key or "").strip()
    key_env = (settings.dify_api_key or "").strip()
    configured = bool(key_db or key_env)
    return KnowledgeBasePublic(
        dify_base_url=url,
        dify_dataset_name_prefix=(row.dify_dataset_name_prefix or "").strip(),
        api_key_configured=configured,
    )


@router.get("/knowledge-base/datasets", response_model=list[DifyDatasetItem])
def list_dify_datasets(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DifyDatasetItem]:
    """代理 Dify 知识库列表（使用服务端保存的 Dataset API 配置）。"""
    url, key = get_dify_url_and_key(db)
    name_prefix = get_dify_dataset_name_prefix(db)
    try:
        rows = list_dataset_catalog(url, key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            detail = (e.response.text or "")[:500]
        except Exception:
            detail = ""
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Dify 请求失败（{e.response.status_code}）{': ' + detail if detail else ''}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"无法连接 Dify: {e!s}",
        ) from e
    if name_prefix:
        rows = [r for r in rows if (r.get("name") or "").startswith(name_prefix)]
    return [DifyDatasetItem(id=r["id"], name=r.get("name") or "") for r in rows]


@router.post("/knowledge-base/test", response_model=KnowledgeBaseTestResult)
def test_dify_knowledge_base(
    body: KnowledgeBaseTestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> KnowledgeBaseTestResult:
    """Test Dataset API connectivity without persisting the submitted values."""

    started = perf_counter()
    saved_url, saved_key = get_dify_url_and_key(db)
    base_url = body.dify_base_url or saved_url
    api_key = body.dify_api_key or saved_key
    prefix = (
        body.dify_dataset_name_prefix
        if body.dify_dataset_name_prefix is not None
        else get_dify_dataset_name_prefix(db)
    )
    try:
        rows = list_dataset_catalog(base_url, api_key)
        if prefix:
            rows = [row for row in rows if (row.get("name") or "").startswith(prefix)]
        datasets = [
            DifyDatasetItem(id=row["id"], name=row.get("name") or "")
            for row in rows[:10]
        ]
        count = len(rows)
        detail = f"Dataset API 目录连接成功，发现 {count} 个符合条件的知识库"
        if prefix and count == 0:
            detail += f"（当前名称前缀：{prefix}）"
        if rows:
            retrieval_errors: list[str] = []
            retrieval_ok = 0
            for row in rows[:3]:
                try:
                    retrieve_dataset_chunks(
                        base_url,
                        api_key,
                        str(row["id"]),
                        body.test_query or "脚手架安全技术要求",
                        top_k=1,
                        timeout=20.0,
                    )
                    retrieval_ok += 1
                except Exception:
                    retrieval_errors.append(row.get("name") or str(row.get("id") or "未知知识库"))
            if retrieval_ok == 0:
                return KnowledgeBaseTestResult(
                    ok=False,
                    status="retrieval_failed",
                    detail=(
                        f"目录可以访问（{count} 个知识库），但实际检索失败；"
                        f"请检查知识库嵌入模型、索引状态和 Dataset API 权限。"
                        f"失败样本：{', '.join(retrieval_errors)}"
                    ),
                    latency_ms=int((perf_counter() - started) * 1000),
                    dataset_count=count,
                    datasets=datasets,
                )
            detail += f"；实际检索验证成功（{retrieval_ok}/{min(count, 3)}）"
            if retrieval_errors:
                detail += f"，其余失败：{', '.join(retrieval_errors)}"
        return KnowledgeBaseTestResult(
            ok=True,
            status="connected",
            detail=detail,
            latency_ms=int((perf_counter() - started) * 1000),
            dataset_count=count,
            datasets=datasets,
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        detail = f"Dify 返回 HTTP {status_code}；请检查是否使用 Dataset API 密钥"
    except httpx.RequestError as exc:
        detail = f"无法连接 Dify：{type(exc).__name__}"
    except Exception as exc:
        detail = str(exc)[:500]
    return KnowledgeBaseTestResult(
        ok=False,
        status="error",
        detail=detail,
        latency_ms=int((perf_counter() - started) * 1000),
    )
