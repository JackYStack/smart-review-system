from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.projects import create_revision_and_review
from app.api.review_tasks import delete_task
from app.api.rules import create_evidence_source, upsert_task_parameters
from app.models.review_governance import ReviewIssue, ReviewRound
from app.models.rule_engine import ParameterValue
from app.models.scheme_review_task import (
    CompletenessStatus,
    ReviewTaskStatus,
    SchemeReviewTask,
)
from app.models.user import User, UserRole
from app.schemas.rule_engine import EvidenceSourceCreate, ParameterValueUpsert
from app.services.expert_review import claim_round, release_round
from app.services.scheme_readiness import SchemeReadinessResult


def _user(user_id: int, role: UserRole) -> User:
    row = MagicMock(spec=User)
    row.id = user_id
    row.role = role
    row.username = f"user-{user_id}"
    return row


def _task(*, status: str = ReviewTaskStatus.succeeded) -> MagicMock:
    task = MagicMock(spec=SchemeReviewTask)
    task.id = 11
    task.user_id = 1
    task.status = status
    task.completeness_status = (
        CompletenessStatus.complete
        if status == ReviewTaskStatus.succeeded
        else CompletenessStatus.unavailable
    )
    task.human_status = "pending"
    task.object_key = "reviews/1/source.docx"
    task.output_object_key = "reviews/1/output.docx"
    return task


def _round(task: MagicMock, *, status: str = "pending") -> MagicMock:
    row = MagicMock(spec=ReviewRound)
    row.id = 21
    row.task = task
    row.task_id = task.id
    row.status = status
    row.assigned_expert_id = None
    row.claim_expires_at = None
    return row


def test_failed_ai_task_cannot_be_claimed_for_formal_review() -> None:
    row = _round(_task(status=ReviewTaskStatus.failed))
    with pytest.raises(ValueError, match="AI审核"):
        claim_round(MagicMock(), row, _user(2, UserRole.expert))


def test_active_claim_without_expiry_cannot_be_stolen() -> None:
    row = _round(_task(), status="in_review")
    row.assigned_expert_id = 2
    row.claim_expires_at = None
    with pytest.raises(ValueError, match="其他专家"):
        claim_round(MagicMock(), row, _user(3, UserRole.expert))


def test_naive_mysql_claim_timestamp_is_compared_safely() -> None:
    row = _round(_task(), status="in_review")
    row.assigned_expert_id = 2
    row.claim_expires_at = datetime.utcnow() - timedelta(minutes=1)
    claim_round(MagicMock(), row, _user(3, UserRole.expert))
    assert row.assigned_expert_id == 3


def test_approved_round_cannot_be_released_back_to_pending() -> None:
    row = _round(_task(), status="approved")
    row.assigned_expert_id = 2
    with pytest.raises(ValueError, match="审阅中"):
        release_round(MagicMock(), row, _user(2, UserRole.expert))


@patch("app.api.review_tasks.minio_storage.remove_object_if_exists")
@patch("app.api.review_tasks.minio_storage.remove_objects_with_prefix")
def test_governed_task_delete_is_rejected_before_storage_mutation(
    remove_prefix: MagicMock, remove_object: MagicMock
) -> None:
    task = _task()
    db = MagicMock()
    db.get.return_value = task
    db.query.return_value.filter.return_value.first.return_value = (21,)
    with pytest.raises(HTTPException) as raised:
        delete_task(task.id, db=db, user=_user(1, UserRole.user))
    assert raised.value.status_code == 409
    remove_prefix.assert_not_called()
    remove_object.assert_not_called()


def test_ordinary_owner_cannot_self_verify_parameters() -> None:
    db = MagicMock()
    db.get.return_value = _task()
    body = [
        ParameterValueUpsert(
            parameter_name="搭设高度",
            raw_value="24m",
            numeric_value=Decimal("24"),
            unit="m",
            verified=True,
        )
    ]
    with pytest.raises(HTTPException) as raised:
        upsert_task_parameters(11, body, db=db, user=_user(1, UserRole.user))
    assert raised.value.status_code == 403


def test_editing_parameter_clears_stale_expert_verification() -> None:
    task = _task()
    parameter = ParameterValue(
        id=8,
        task_id=task.id,
        parameter_name="搭设高度",
        raw_value="24m",
        numeric_value=Decimal("24"),
        unit="m",
        normalized_value=Decimal("24"),
        normalized_unit="m",
        source_json="{}",
        extraction_method="manual",
        verified_by_id=2,
        verified_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db = MagicMock()
    db.get.return_value = task
    query = db.query.return_value
    query.filter.return_value.first.return_value = parameter
    query.filter.return_value.order_by.return_value.all.return_value = [parameter]
    upsert_task_parameters(
        task.id,
        [
            ParameterValueUpsert(
                parameter_name="搭设高度",
                raw_value="25m",
                numeric_value=Decimal("25"),
                unit="m",
            )
        ],
        db=db,
        user=_user(1, UserRole.user),
    )
    assert parameter.verified_by_id is None
    assert parameter.verified_at is None


def test_evidence_cannot_link_issue_from_another_task() -> None:
    task = _task()
    issue = MagicMock(spec=ReviewIssue)
    issue.id = 91
    issue.review_round_id = 92
    db = MagicMock()

    def get(model, object_id):
        if model is SchemeReviewTask:
            return task
        if model is ReviewIssue:
            return issue
        return None

    db.get.side_effect = get
    db.query.return_value.filter.return_value.scalar.return_value = 999
    with pytest.raises(HTTPException) as raised:
        create_evidence_source(
            task.id,
            EvidenceSourceCreate(
                review_issue_id=issue.id,
                standard_no="JGJ 130-2011",
                clause_no="6.4.3",
                clause_text="连墙件设置要求",
            ),
            db=db,
            user=_user(7, UserRole.admin),
        )
    assert raised.value.status_code == 400


@patch("app.api.projects.assess_scheme_readiness")
def test_revision_parent_must_have_same_scheme_type(assess: MagicMock) -> None:
    project = MagicMock()
    project.id = 1
    project.created_by_id = 1
    project.archived_at = None
    scheme = MagicMock()
    scheme.id = 10
    scheme.lifecycle_status = "published"
    parent = MagicMock()
    parent.id = 3
    parent.project_id = 1
    parent.scheme_type_id = 99
    template = MagicMock()
    db = MagicMock()

    def get(model, object_id):
        name = model.__name__
        if name == "Project":
            return project
        if name == "SchemeType":
            return scheme
        if name == "DocumentRevision":
            return parent
        return None

    db.get.side_effect = get
    db.query.return_value.filter.return_value.first.return_value = template
    assess.return_value = SchemeReadinessResult(status="ready", issues=())
    upload = MagicMock()
    upload.filename = "方案.docx"
    upload.read = AsyncMock(return_value=b"should-not-be-read")

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            create_revision_and_review(
                project_id=1,
                scheme_type_id=10,
                version_label="V2",
                parent_revision_id=3,
                file=upload,
                db=db,
                user=_user(1, UserRole.user),
            )
        )
    assert raised.value.status_code == 400
    upload.read.assert_not_awaited()
