from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base
from app.models.scheme_review_task import ReviewTaskStatus, SchemeReviewTask
from app.models.scheme_type import SchemeType
from app.models.user import User, UserRole
from app.services.review_task_worker import _renew_task_leases


def test_worker_heartbeat_renews_only_its_live_processing_leases() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(username="owner", phone="13900000001", password_hash="x", role=UserRole.user)
    scheme = SchemeType(category="脚手架", name="落地式")
    db.add_all([user, scheme])
    db.flush()

    own = SchemeReviewTask(
        scheme_type_id=scheme.id,
        user_id=user.id,
        status=ReviewTaskStatus.processing,
        lease_owner="worker-a",
        minio_bucket="review",
        object_key="own.docx",
        original_filename="own.docx",
    )
    other = SchemeReviewTask(
        scheme_type_id=scheme.id,
        user_id=user.id,
        status=ReviewTaskStatus.processing,
        lease_owner="worker-b",
        minio_bucket="review",
        object_key="other.docx",
        original_filename="other.docx",
    )
    db.add_all([own, other])
    db.commit()

    before = datetime.now(UTC)
    assert _renew_task_leases(
        db,
        "worker-a",
        [own.id, other.id],
        lease_seconds=1800,
    ) == 1
    db.commit()
    db.refresh(own)
    db.refresh(other)
    assert own.lease_expires_at is not None
    own_expiry = own.lease_expires_at
    if own_expiry.tzinfo is None:
        own_expiry = own_expiry.replace(tzinfo=UTC)
    assert own_expiry > before
    assert other.lease_expires_at is None

    db.close()
    engine.dispose()
