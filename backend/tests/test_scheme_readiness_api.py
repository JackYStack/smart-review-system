from __future__ import annotations

from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.api.review_tasks import create_task
from app.api.scheme_types import get_scheme_readiness
from app.services.scheme_readiness import SchemeReadinessResult


class TestSchemeReadinessEndpoint(TestCase):
    @patch("app.api.scheme_types.assess_scheme_readiness")
    def test_returns_stable_readiness_contract(self, assess: MagicMock) -> None:
        row = MagicMock()
        row.id = 7
        db = MagicMock()
        db.query.return_value.options.return_value.filter.return_value.first.return_value = row
        assess.return_value = SchemeReadinessResult(
            status="incomplete",
            issues=("内容审核未配置提示词",),
        )

        response = get_scheme_readiness(7, db=db, _=MagicMock())

        self.assertEqual(response.scheme_type_id, 7)
        self.assertEqual(response.readiness_status, "incomplete")
        self.assertEqual(response.readiness_issues, ["内容审核未配置提示词"])


class TestReviewSubmissionReadinessGate(IsolatedAsyncioTestCase):
    @patch("app.api.review_tasks.minio_storage.put_object")
    @patch("app.api.review_tasks.assess_scheme_readiness")
    async def test_incomplete_scheme_is_rejected_before_file_or_storage_access(
        self,
        assess: MagicMock,
        put_object: MagicMock,
    ) -> None:
        scheme = MagicMock()
        scheme.id = 7
        template = MagicMock()
        db = MagicMock()
        db.get.return_value = scheme
        db.query.return_value.filter.return_value.first.return_value = template
        assess.return_value = SchemeReadinessResult(
            status="incomplete",
            issues=("内容审核未配置提示词",),
        )
        upload = MagicMock()
        upload.filename = "scheme.docx"
        upload.read = AsyncMock(return_value=b"not-read")

        with self.assertRaises(HTTPException) as raised:
            await create_task(
                scheme_type_id=7,
                file=upload,
                db=db,
                user=MagicMock(),
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "scheme_not_ready",
                "readiness_status": "incomplete",
                "readiness_issues": ["内容审核未配置提示词"],
            },
        )
        upload.read.assert_not_awaited()
        put_object.assert_not_called()
