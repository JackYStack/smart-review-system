from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.models.scheme_review_task import SchemeReviewTask
from app.models.scheme_workflow_profile import SchemeDifyWorkflowProfile
from app.schemas.scheme_workflow_profile import SchemeWorkflowProfileUpdate
from app.services.scheme_workflow_profile import (
    EffectiveSchemeWorkflowProfile,
    resolve_task_workflow_snapshot,
    snapshot_task_workflow,
    upsert_scheme_workflow_profile,
    workflow_profile_public,
)
from app.services.secret_store import decrypt_secret, is_encrypted


def _effective() -> EffectiveSchemeWorkflowProfile:
    return EffectiveSchemeWorkflowProfile(
        profile_id=12,
        version=3,
        source="scheme_profile",
        enabled=True,
        base_url="https://dify.example/v1",
        api_key="app-secret-value",
        user_prefix="scaffold",
        timeout_seconds=600,
        output_variable="report",
        output_format="json",
        accept_partial=False,
        continue_on_failure=True,
        input_mapping={
            "documents": "scheme_files",
            "project_name": "project",
            "project_region": "region",
            "risk_type": "risk",
            "review_focus": "focus",
        },
    )


def test_public_profile_masks_api_key() -> None:
    public = workflow_profile_public(5, _effective())
    payload = public.model_dump()
    assert payload["api_key_configured"] is True
    assert "api_key" not in payload
    assert "app-secret-value" not in json.dumps(payload, ensure_ascii=False)


@patch(
    "app.services.scheme_workflow_profile.resolve_scheme_workflow_profile",
    return_value=_effective(),
)
def test_task_snapshot_freezes_inputs_and_only_encrypted_config(_resolve: MagicMock) -> None:
    task = SchemeReviewTask(
        scheme_type_id=5,
        user_id=8,
        minio_bucket="review",
        object_key="reviews/5/source.docx",
        original_filename="脚手架方案.docx",
    )
    snapshot_task_workflow(
        MagicMock(),
        task,
        scheme_category="脚手架工程",
        scheme_name="落地式脚手架",
        project_name="东区项目",
        project_region="南京市",
        review_focus="重点检查连墙件",
    )

    assert task.dify_workflow_profile_id == 12
    assert task.dify_workflow_profile_version == 3
    assert "app-secret-value" not in (task.dify_workflow_config_snapshot or "")
    config = json.loads(task.dify_workflow_config_snapshot or "{}")
    assert is_encrypted(config["api_key_ciphertext"])
    assert decrypt_secret(config["api_key_ciphertext"]) == "app-secret-value"
    inputs = json.loads(task.dify_workflow_inputs_snapshot or "{}")
    assert inputs["project_name"] == "东区项目"
    assert inputs["project_region"] == "南京市"
    assert inputs["review_focus"] == "重点检查连墙件"

    restored = resolve_task_workflow_snapshot(
        MagicMock(),
        task,
        scheme_category="ignored",
        scheme_name="ignored",
    )
    assert restored.config.profile_id == 12
    assert restored.config.version == 3
    assert restored.config.api_key == "app-secret-value"
    assert restored.inputs == inputs


@patch("app.services.scheme_workflow_profile.get_scheme_workflow_profile")
def test_profile_upsert_encrypts_key_and_increments_version(get_row: MagicMock) -> None:
    row = SchemeDifyWorkflowProfile(
        id=2,
        scheme_type_id=5,
        version=4,
        enabled=True,
        base_url="https://old.example/v1",
        api_key=None,
        user_prefix="old",
        timeout_seconds=900,
        output_variable="report",
        output_format="json",
        accept_partial=True,
        continue_on_failure=True,
        input_mapping="{}",
    )
    get_row.return_value = row
    body = SchemeWorkflowProfileUpdate(
        enabled=True,
        base_url="https://new.example/v1/",
        api_key="new-app-key",
    )

    updated = upsert_scheme_workflow_profile(MagicMock(), 5, body)

    assert updated.version == 5
    assert updated.base_url == "https://new.example/v1"
    assert is_encrypted(updated.api_key)
    assert decrypt_secret(updated.api_key) == "new-app-key"
    assert "new-app-key" not in (updated.api_key or "")
