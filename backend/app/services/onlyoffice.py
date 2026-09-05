from __future__ import annotations

import hashlib
import io
import socket
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.scheme_review_task import SchemeReviewTask
from app.models.user import User
from app.services.onlyoffice_settings import EffectiveOnlyoffice, get_effective_onlyoffice

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
ONLYOFFICE_CALLBACK_MAX_BYTES = 100 * 1024 * 1024
ONLYOFFICE_DOCX_MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
ONLYOFFICE_DOCX_MAX_ENTRIES = 20_000
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document.main+xml"
)


def _is_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname.lower() in LOOPBACK_HOSTS


def _replace_url_host(base_url: str, new_host: str) -> str:
    parts = urlsplit(base_url)
    if not parts.hostname:
        return base_url.rstrip("/")
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{new_host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)).rstrip("/")


def _detect_local_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            outbound_ip = sock.getsockname()[0]
            if outbound_ip and not _is_loopback_host(outbound_ip):
                return outbound_ip
    except OSError:
        pass
    try:
        hostname_ip = socket.gethostbyname(socket.gethostname())
        if hostname_ip and not _is_loopback_host(hostname_ip):
            return hostname_ip
    except OSError:
        return None
    return None


def resolve_onlyoffice_public_base_url(callback_base_url: str) -> str:
    base_url = callback_base_url.rstrip("/")
    base_host = urlsplit(base_url).hostname
    if _is_loopback_host(base_host):
        lan_ip = _detect_local_lan_ip()
        if lan_ip:
            return _replace_url_host(base_url, lan_ip)
    return base_url


def build_doc_key(task: SchemeReviewTask) -> str:
    # Keep the key stable for the lifetime of an editor session.  In particular,
    # a force-save changes output_object_key/updated_at, but subsequent callbacks
    # from that same editor must remain bound to this task and source document.
    raw = f"{task.id}:{task.object_key or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_file_access_token(task_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(hours=1)
    payload = {
        "purpose": "onlyoffice_file",
        "tid": task_id,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_file_access_token(token: str) -> int | None:
    settings = get_settings()
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if data.get("purpose") != "onlyoffice_file":
        return None
    tid = data.get("tid")
    if not isinstance(tid, int):
        return None
    return tid


def make_editor_token(config: dict[str, Any], oo_jwt_secret: str) -> str:
    return jwt.encode(config, oo_jwt_secret, algorithm="HS256")


def verify_callback_token(
    token: str,
    oo_jwt_secret: str,
    *,
    key: str,
    status: int,
    url: str | None,
) -> None:
    """Verify that the callback body is the body signed by Document Server."""
    if not token or not oo_jwt_secret:
        raise ValueError("missing callback token or JWT secret")
    try:
        decoded = jwt.decode(token, oo_jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("invalid callback token") from exc
    if not isinstance(decoded, dict):
        raise ValueError("invalid callback token payload")
    signed = decoded.get("payload", decoded)
    if not isinstance(signed, dict):
        raise ValueError("invalid callback token payload")
    if signed.get("key") != key or signed.get("status") != status:
        raise ValueError("callback token does not match request body")
    if signed.get("url") != url:
        raise ValueError("callback token does not match request URL")


def extract_bearer_token(authorization: str | None) -> str:
    value = (authorization or "").strip()
    scheme, separator, token = value.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise ValueError("missing bearer token")
    return token.strip()


def build_editor_config(
    *,
    task: SchemeReviewTask,
    user: User,
    eff: EffectiveOnlyoffice,
    file_token: str,
    view_only: bool = False,
    document_key: str | None = None,
    callback_session_id: int | None = None,
) -> dict[str, Any]:
    public_base = resolve_onlyoffice_public_base_url(eff.callback_base_url)
    file_url = (
        f"{public_base}/review-tasks/{task.id}/onlyoffice/document"
        f"?token={quote(file_token, safe='')}"
    )
    title = (task.original_filename or "document.docx").strip() or "document.docx"
    editor_cfg: dict[str, Any] = {
        "mode": "view" if view_only else "edit",
        "lang": eff.editor_lang,
        "user": {"id": str(user.id), "name": user.username or f"user-{user.id}"},
        "customization": {
            "compactToolbar": True,
            "compactHeader": True,
            "toolbarHideFileName": True,
            # Ensure users can trigger explicit save, so callback pushes
            # the latest content before export/download.
            "forcesave": True,
        },
    }
    if not view_only:
        if callback_session_id is None:
            raise ValueError("OnlyOffice edit mode requires a callback session")
        editor_cfg["callbackUrl"] = (
            f"{public_base}/onlyoffice/callback?task_id={task.id}"
            f"&session_id={callback_session_id}"
        )
    return {
        "document": {
            "fileType": "docx",
            "key": document_key or build_doc_key(task),
            "title": title,
            "url": file_url,
        },
        "documentType": "word",
        "editorConfig": editor_cfg,
        "permissions": {
            "edit": not view_only,
            "comment": not view_only,
            "review": not view_only,
            "download": True,
            "print": True,
        },
    }


def _url_origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("OnlyOffice URL must be an absolute HTTP(S) URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("OnlyOffice URL must not contain credentials")
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("OnlyOffice URL has an invalid port") from exc
    return scheme, parts.hostname.lower().rstrip("."), port


def validate_callback_download_url(url: str, docs_url: str) -> None:
    """Allow callback downloads only from the configured Document Server origin."""
    if _url_origin(url) != _url_origin(docs_url):
        raise ValueError("callback URL is not on the configured OnlyOffice Document Server")


def validate_docx_ooxml(content: bytes) -> None:
    """Reject non-DOCX ZIPs and obviously hostile/malformed OOXML packages."""
    if not content or not zipfile.is_zipfile(io.BytesIO(content)):
        raise ValueError("callback response is not an OOXML ZIP package")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as package:
            entries = package.infolist()
            if len(entries) > ONLYOFFICE_DOCX_MAX_ENTRIES:
                raise ValueError("DOCX package contains too many entries")
            names = [entry.filename.replace("\\", "/") for entry in entries]
            if len(names) != len(set(names)):
                raise ValueError("DOCX package contains duplicate entries")
            required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
            if not required.issubset(names):
                raise ValueError("callback response is not a Word OOXML document")
            total_uncompressed = 0
            for entry, name in zip(entries, names, strict=True):
                if entry.flag_bits & 0x1:
                    raise ValueError("encrypted DOCX entries are not accepted")
                path_parts = name.split("/")
                if name.startswith("/") or ".." in path_parts:
                    raise ValueError("unsafe path in DOCX package")
                total_uncompressed += entry.file_size
                if total_uncompressed > ONLYOFFICE_DOCX_MAX_UNCOMPRESSED_BYTES:
                    raise ValueError("DOCX package expands beyond the allowed size")
            content_types = ElementTree.fromstring(package.read("[Content_Types].xml"))
            document_type_found = any(
                element.attrib.get("PartName") == "/word/document.xml"
                and element.attrib.get("ContentType") == DOCX_CONTENT_TYPE
                for element in content_types
            )
            if not document_type_found:
                raise ValueError("OOXML package does not declare a DOCX main document")
            ElementTree.fromstring(package.read("_rels/.rels"))
            ElementTree.fromstring(package.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ValueError("callback response contains malformed OOXML") from exc


async def _pull_callback_file(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
) -> bytes:
    async with client.stream("GET", url, follow_redirects=False) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("OnlyOffice callback download redirect is not allowed")
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = None
            if declared_length is not None and declared_length > max_bytes:
                raise ValueError("OnlyOffice callback document exceeds the size limit")
        chunks: list[bytes] = []
        received = 0
        async for chunk in response.aiter_bytes():
            received += len(chunk)
            if received > max_bytes:
                raise ValueError("OnlyOffice callback document exceeds the size limit")
            chunks.append(chunk)
        return b"".join(chunks)


async def pull_callback_file(
    url: str,
    docs_url: str,
    *,
    max_bytes: int = ONLYOFFICE_CALLBACK_MAX_BYTES,
    client: httpx.AsyncClient | None = None,
) -> bytes:
    validate_callback_download_url(url, docs_url)
    if max_bytes <= 0:
        raise ValueError("callback size limit must be positive")
    if client is not None:
        content = await _pull_callback_file(client, url, max_bytes=max_bytes)
    else:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=False) as owned_client:
            content = await _pull_callback_file(owned_client, url, max_bytes=max_bytes)
    validate_docx_ooxml(content)
    return content


def assert_onlyoffice_ready(db: Session) -> EffectiveOnlyoffice:
    eff = get_effective_onlyoffice(db)
    if not eff.docs_url or not eff.jwt_secret or not eff.callback_base_url:
        raise ValueError("OnlyOffice 未配置完整：请在「设置」或环境变量中填写 Docs 地址、JWT 密钥与回调基址")
    return eff
