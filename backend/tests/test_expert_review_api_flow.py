from __future__ import annotations

import hashlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register every FK target in Base.metadata
from app.api import expert_reviews
from app.database import Base, get_db
from app.deps import get_current_user
from app.models.review_governance import ReviewIssue, ReviewRound
from app.models.scheme_review_task import (
    CompletenessStatus,
    ReviewTaskStatus,
    SchemeReviewTask,
)
from app.models.scheme_type import SchemeType
from app.models.user import User, UserRole


def test_expert_claim_decide_approve_and_manager_sign_flow(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db: Session = session_factory()

    owner = User(
        username="owner",
        phone="13000000001",
        password_hash="x",
        role=UserRole.user,
    )
    expert = User(
        username="expert",
        phone="13000000002",
        password_hash="x",
        role=UserRole.expert,
    )
    manager = User(
        username="manager",
        phone="13000000003",
        password_hash="x",
        role=UserRole.review_admin,
    )
    scheme = SchemeType(category="脚手架工程", name="落地式脚手架")
    db.add_all([owner, expert, manager, scheme])
    db.flush()
    task = SchemeReviewTask(
        scheme_type_id=scheme.id,
        user_id=owner.id,
        status=ReviewTaskStatus.succeeded,
        completeness_status=CompletenessStatus.complete,
        review_conclusion="issues_found",
        minio_bucket="review",
        object_key="reviews/source.docx",
        output_object_key="reviews/annotated.docx",
        original_filename="脚手架方案.docx",
        review_result_json='{"schema_version":"1.0","steps":[]}',
    )
    db.add(task)
    db.flush()
    review_round = ReviewRound(task_id=task.id, round_no=1, status="pending")
    db.add(review_round)
    db.flush()
    issue = ReviewIssue(
        review_round_id=review_round.id,
        issue_key="issue-1",
        source_issue_id="issue-1",
        step_id="content",
        severity="error",
        message="缺少连墙件验算",
        evidence="方案原文未见验算",
        anchor_json="{}",
        related_json="{}",
    )
    db.add(issue)
    db.commit()

    app = FastAPI()
    app.include_router(expert_reviews.router)
    current = {"user": expert}

    def override_db():
        yield db

    def override_user():
        return current["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)

    claimed = client.post(f"/expert/review-rounds/{review_round.id}/claim")
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "in_review"
    assert claimed.json()["assigned_expert_id"] == expert.id

    decided = client.patch(
        f"/expert/review-rounds/{review_round.id}/issues/{issue.id}",
        json={
            "disposition": "accepted",
            "reviewer_comment": "确认该问题，要求补充验算",
            "final_severity": "error",
        },
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["disposition"] == "accepted"

    approved = client.post(
        f"/expert/review-rounds/{review_round.id}/approve",
        json={"comment": "逐项复核完成", "conclusion": "conditional_pass"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    current["user"] = manager
    report_bytes = b"signed-docx-placeholder"
    digest = hashlib.sha256(report_bytes).hexdigest()
    stored: dict[str, object] = {}

    def fake_put(key, content, *, length, content_type):
        stored.update(key=key, content=content, length=length, content_type=content_type)

    monkeypatch.setattr(expert_reviews, "build_signed_report", lambda *_a, **_k: (report_bytes, digest))
    monkeypatch.setattr(expert_reviews.minio_storage, "put_object", fake_put)
    signed = client.post(f"/expert/review-rounds/{review_round.id}/sign")
    assert signed.status_code == 200, signed.text
    assert signed.json()["status"] == "signed"
    assert signed.json()["signed_report_available"] is True
    assert stored["content"] == report_bytes

    # Immutable final state: even a manager cannot release a signed round.
    release = client.post(
        f"/expert/review-rounds/{review_round.id}/release",
        json={"comment": "try to reopen"},
    )
    assert release.status_code == 409

    db.close()
    engine.dispose()
