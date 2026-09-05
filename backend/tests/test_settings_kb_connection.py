from unittest.mock import Mock, patch

import httpx

from app.api.settings_kb import test_dify_knowledge_base as _run_knowledge_base_test
from app.schemas.knowledge_base import KnowledgeBaseTestRequest


def test_knowledge_base_connection_uses_submitted_values_and_filters_prefix() -> None:
    db = Mock()
    with (
        patch(
            "app.api.settings_kb.get_dify_url_and_key",
            return_value=("http://saved/v1", "saved-key"),
        ),
        patch(
            "app.api.settings_kb.list_dataset_catalog",
            return_value=[
                {"id": "1", "name": "危大-脚手架"},
                {"id": "2", "name": "其他知识库"},
            ],
        ) as catalog,
        patch("app.api.settings_kb.retrieve_dataset_chunks", return_value="法规片段") as retrieve,
    ):
        result = _run_knowledge_base_test(
            KnowledgeBaseTestRequest(
                dify_base_url="http://new/v1",
                dify_dataset_name_prefix="危大-",
                dify_api_key="dataset-key",
            ),
            db,
            Mock(),
        )
    assert result.ok is True
    assert result.dataset_count == 1
    assert result.datasets[0].name == "危大-脚手架"
    catalog.assert_called_once_with("http://new/v1", "dataset-key")
    retrieve.assert_called_once()


def test_knowledge_base_connection_reuses_saved_key_when_field_is_blank() -> None:
    db = Mock()
    with (
        patch(
            "app.api.settings_kb.get_dify_url_and_key",
            return_value=("http://saved/v1", "saved-key"),
        ),
        patch("app.api.settings_kb.list_dataset_catalog", return_value=[]) as catalog,
    ):
        result = _run_knowledge_base_test(
            KnowledgeBaseTestRequest(dify_base_url="", dify_api_key=""),
            db,
            Mock(),
        )
    assert result.ok is True
    catalog.assert_called_once_with("http://saved/v1", "saved-key")


def test_knowledge_base_connection_reports_real_retrieval_failure() -> None:
    db = Mock()
    with (
        patch(
            "app.api.settings_kb.get_dify_url_and_key",
            return_value=("http://dify/v1", "dataset-key"),
        ),
        patch("app.api.settings_kb.get_dify_dataset_name_prefix", return_value=""),
        patch(
            "app.api.settings_kb.list_dataset_catalog",
            return_value=[{"id": "1", "name": "法规知识库"}],
        ),
        patch(
            "app.api.settings_kb.retrieve_dataset_chunks",
            side_effect=ValueError("remote secret detail"),
        ),
    ):
        result = _run_knowledge_base_test(KnowledgeBaseTestRequest(), db, Mock())
    assert result.ok is False
    assert result.status == "retrieval_failed"
    assert result.dataset_count == 1
    assert "实际检索失败" in result.detail
    assert "remote secret detail" not in result.detail


def test_knowledge_base_connection_hides_remote_response_body() -> None:
    db = Mock()
    request = httpx.Request("GET", "http://dify/v1/datasets")
    response = httpx.Response(401, request=request, text="secret remote response")
    error = httpx.HTTPStatusError("unauthorized", request=request, response=response)
    with (
        patch(
            "app.api.settings_kb.get_dify_url_and_key",
            return_value=("http://dify/v1", "bad-key"),
        ),
        patch("app.api.settings_kb.list_dataset_catalog", side_effect=error),
    ):
        result = _run_knowledge_base_test(KnowledgeBaseTestRequest(), db, Mock())
    assert result.ok is False
    assert "401" in result.detail
    assert "secret remote response" not in result.detail
