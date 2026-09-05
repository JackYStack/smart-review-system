from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime, timedelta
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from jose import jwt

from app.api.onlyoffice_callback import onlyoffice_callback
from app.models.scheme_review_task import ReviewTaskStatus
from app.models.document_artifact import OnlyofficeEditSession
from app.schemas.onlyoffice_editor import OnlyofficeCallbackPayload
from app.services.onlyoffice import (
    DOCX_CONTENT_TYPE,
    build_doc_key,
    pull_callback_file,
    validate_callback_download_url,
    validate_docx_ooxml,
    verify_callback_token,
)
from app.services.onlyoffice_settings import EffectiveOnlyoffice


def _docx_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                f'<Override PartName="/word/document.xml" ContentType="{DOCX_CONTENT_TYPE}"/>'
                "</Types>"
            ),
        )
        package.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        package.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
        )
    return stream.getvalue()


def _task() -> MagicMock:
    task = MagicMock()
    task.id = 17
    task.scheme_type_id = 4
    task.status = ReviewTaskStatus.succeeded
    task.object_key = "reviews/4/source.docx"
    task.output_object_key = "reviews/4/annotated.docx"
    task.minio_bucket = "review"
    task.original_filename = "方案.docx"
    task.updated_at = None
    return task


def _edit_session(task: MagicMock, document_key: str) -> MagicMock:
    session = MagicMock(spec=OnlyofficeEditSession)
    session.id = 31
    session.task_id = task.id
    session.document_key = document_key
    session.source_object_key = task.output_object_key
    session.current_object_key = task.output_object_key
    session.expires_at = datetime.now(UTC) + timedelta(hours=1)
    session.closed_at = None
    return session


class TestOnlyofficeCallbackValidation(TestCase):
    def test_document_key_is_stable_across_callback_versions(self) -> None:
        task = _task()
        original_key = build_doc_key(task)
        task.output_object_key = "reviews/4/onlyoffice/17/version-2.docx"
        self.assertEqual(build_doc_key(task), original_key)

    def test_callback_token_must_sign_key_status_and_url(self) -> None:
        secret = "callback-secret"
        signed = {
            "key": "document-key",
            "status": 2,
            "url": "https://office.example.test/cache/file.docx",
        }
        token = jwt.encode({"payload": signed}, secret, algorithm="HS256")
        verify_callback_token(token, secret, **signed)
        with self.assertRaises(ValueError):
            verify_callback_token(token, secret, **{**signed, "key": "another-task"})

    def test_callback_url_must_match_configured_document_server_origin(self) -> None:
        validate_callback_download_url(
            "https://office.example.test/cache/file.docx?token=abc",
            "https://office.example.test/",
        )
        with self.assertRaises(ValueError):
            validate_callback_download_url(
                "https://attacker.example.test/file.docx",
                "https://office.example.test/",
            )
        with self.assertRaises(ValueError):
            validate_callback_download_url(
                "https://office.example.test:8443/file.docx",
                "https://office.example.test/",
            )

    def test_docx_validation_rejects_plain_zip(self) -> None:
        validate_docx_ooxml(_docx_bytes())
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as package:
            package.writestr("message.txt", "not a docx")
        with self.assertRaises(ValueError):
            validate_docx_ooxml(stream.getvalue())


class TestOnlyofficeCallbackDownload(IsolatedAsyncioTestCase):
    async def test_redirect_is_never_followed(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                302,
                headers={"location": "http://127.0.0.1/private"},
                request=request,
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaisesRegex(ValueError, "redirect"):
                await pull_callback_file(
                    "https://office.example.test/cache/file.docx",
                    "https://office.example.test",
                    client=client,
                )

    async def test_streamed_response_size_is_limited(self) -> None:
        content = _docx_bytes()
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, content=content, request=request)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaisesRegex(ValueError, "size limit"):
                await pull_callback_file(
                    "https://office.example.test/cache/file.docx",
                    "https://office.example.test",
                    max_bytes=len(content) - 1,
                    client=client,
                )


class TestOnlyofficeCallbackEndpoint(IsolatedAsyncioTestCase):
    async def test_valid_callback_saves_new_object_and_updates_pointer(self) -> None:
        task = _task()
        old_object_key = task.output_object_key
        document_key = "session-document-key"
        edit_session = _edit_session(task, document_key)
        url = "https://office.example.test/cache/file.docx"
        payload = OnlyofficeCallbackPayload(key=document_key, status=2, url=url)
        secret = "callback-secret"
        token = jwt.encode(
            {"payload": {"key": document_key, "status": 2, "url": url}},
            secret,
            algorithm="HS256",
        )
        db = MagicMock()
        db.get.side_effect = lambda model, object_id: (
            task if model.__name__ == "SchemeReviewTask" else edit_session
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        effective = EffectiveOnlyoffice(
            docs_url="https://office.example.test",
            jwt_secret=secret,
            callback_base_url="https://api.example.test",
            editor_lang="zh",
        )

        with (
            patch(
                "app.api.onlyoffice_callback.get_effective_onlyoffice",
                return_value=effective,
            ),
            patch(
                "app.api.onlyoffice_callback.pull_callback_file",
                new=AsyncMock(return_value=_docx_bytes()),
            ) as download,
            patch("app.api.onlyoffice_callback.minio_storage.put_object") as put_object,
            patch("app.api.onlyoffice_callback.record_document_artifact"),
        ):
            result = await onlyoffice_callback(
                payload,
                task_id=task.id,
                session_id=edit_session.id,
                authorization=f"Bearer {token}",
                db=db,
            )

        self.assertEqual(result, {"error": 0})
        download.assert_awaited_once_with(url, effective.docs_url)
        saved_key = put_object.call_args.args[0]
        self.assertNotEqual(saved_key, old_object_key)
        self.assertEqual(task.output_object_key, saved_key)
        self.assertIn(f"/onlyoffice/{task.id}/", saved_key)
        db.commit.assert_called_once_with()

    async def test_failed_task_cannot_persist_a_partial_editor_document(self) -> None:
        task = _task()
        task.status = ReviewTaskStatus.failed
        document_key = "session-document-key"
        edit_session = _edit_session(task, document_key)
        url = "https://office.example.test/cache/file.docx"
        payload = OnlyofficeCallbackPayload(key=document_key, status=2, url=url)
        secret = "callback-secret"
        token = jwt.encode(
            {"payload": {"key": document_key, "status": 2, "url": url}},
            secret,
            algorithm="HS256",
        )
        db = MagicMock()
        db.get.side_effect = lambda model, object_id: (
            task if model.__name__ == "SchemeReviewTask" else edit_session
        )
        effective = EffectiveOnlyoffice(
            docs_url="https://office.example.test",
            jwt_secret=secret,
            callback_base_url="https://api.example.test",
            editor_lang="zh",
        )

        with (
            patch(
                "app.api.onlyoffice_callback.get_effective_onlyoffice",
                return_value=effective,
            ),
            patch(
                "app.api.onlyoffice_callback.pull_callback_file",
                new=AsyncMock(return_value=_docx_bytes()),
            ) as download,
            patch("app.api.onlyoffice_callback.minio_storage.put_object") as put_object,
        ):
            result = await onlyoffice_callback(
                payload,
                task_id=task.id,
                session_id=edit_session.id,
                authorization=f"Bearer {token}",
                db=db,
            )

        self.assertEqual(result, {"error": 1, "message": "task is not editable"})
        download.assert_not_awaited()
        put_object.assert_not_called()

    async def test_document_key_cannot_be_reused_for_another_task(self) -> None:
        task = _task()
        edit_session = _edit_session(task, "expected-session-key")
        payload = OnlyofficeCallbackPayload(key="wrong-task-key", status=2, url=None)
        secret = "callback-secret"
        token = jwt.encode(
            {"payload": {"key": payload.key, "status": payload.status}},
            secret,
            algorithm="HS256",
        )
        db = MagicMock()
        db.get.side_effect = lambda model, object_id: (
            task if model.__name__ == "SchemeReviewTask" else edit_session
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        effective = EffectiveOnlyoffice(
            docs_url="https://office.example.test",
            jwt_secret=secret,
            callback_base_url="https://api.example.test",
            editor_lang="zh",
        )
        with patch(
            "app.api.onlyoffice_callback.get_effective_onlyoffice",
            return_value=effective,
        ):
            with self.assertRaises(HTTPException) as raised:
                await onlyoffice_callback(
                    payload,
                    task_id=task.id,
                    session_id=edit_session.id,
                    authorization=f"Bearer {token}",
                    db=db,
                )
        self.assertEqual(raised.exception.status_code, 403)

    async def test_stale_edit_session_cannot_overwrite_newer_version(self) -> None:
        task = _task()
        edit_session = _edit_session(task, "session-key")
        task.output_object_key = "reviews/4/newer-session-version.docx"
        payload = OnlyofficeCallbackPayload(key="session-key", status=2, url=None)
        secret = "callback-secret"
        token = jwt.encode(
            {"payload": {"key": payload.key, "status": payload.status}},
            secret,
            algorithm="HS256",
        )
        db = MagicMock()
        db.get.side_effect = lambda model, object_id: (
            task if model.__name__ == "SchemeReviewTask" else edit_session
        )
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        effective = EffectiveOnlyoffice(
            docs_url="https://office.example.test",
            jwt_secret=secret,
            callback_base_url="https://api.example.test",
            editor_lang="zh",
        )
        with patch(
            "app.api.onlyoffice_callback.get_effective_onlyoffice",
            return_value=effective,
        ):
            with self.assertRaises(HTTPException) as raised:
                await onlyoffice_callback(
                    payload,
                    task_id=task.id,
                    session_id=edit_session.id,
                    authorization=f"Bearer {token}",
                    db=db,
                )
        self.assertEqual(raised.exception.status_code, 409)

    async def test_signed_round_rejects_late_editor_callback(self) -> None:
        task = _task()
        payload = OnlyofficeCallbackPayload(key="session-key", status=2, url=None)
        secret = "callback-secret"
        token = jwt.encode(
            {"payload": {"key": payload.key, "status": payload.status}},
            secret,
            algorithm="HS256",
        )
        signed_round = MagicMock()
        signed_round.status = "signed"
        db = MagicMock()
        db.get.return_value = task
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = signed_round
        effective = EffectiveOnlyoffice(
            docs_url="https://office.example.test",
            jwt_secret=secret,
            callback_base_url="https://api.example.test",
            editor_lang="zh",
        )
        with patch(
            "app.api.onlyoffice_callback.get_effective_onlyoffice",
            return_value=effective,
        ):
            with self.assertRaises(HTTPException) as raised:
                await onlyoffice_callback(
                    payload,
                    task_id=task.id,
                    session_id=31,
                    authorization=f"Bearer {token}",
                    db=db,
                )
        self.assertEqual(raised.exception.status_code, 409)

    async def test_unsigned_callback_is_rejected_before_task_lookup(self) -> None:
        db = MagicMock()
        effective = EffectiveOnlyoffice(
            docs_url="https://office.example.test",
            jwt_secret="callback-secret",
            callback_base_url="https://api.example.test",
            editor_lang="zh",
        )
        with patch(
            "app.api.onlyoffice_callback.get_effective_onlyoffice",
            return_value=effective,
        ):
            with self.assertRaises(HTTPException) as raised:
                await onlyoffice_callback(
                    OnlyofficeCallbackPayload(key="key", status=1),
                    task_id=17,
                    session_id=31,
                    authorization=None,
                    db=db,
                )
        self.assertEqual(raised.exception.status_code, 401)
        db.get.assert_not_called()
