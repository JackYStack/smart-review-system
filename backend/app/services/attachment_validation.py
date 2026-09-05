from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

from app.services.upload_validation import UploadValidationError, validate_docx_upload


MAX_SUPPORTING_BYTES = 30 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class ValidatedAttachment:
    extension: str
    content_type: str


def validate_supporting_attachment(
    filename: str | None, data: bytes, *, kind: str
) -> ValidatedAttachment:
    name = (filename or "").strip()
    extension = PurePath(name).suffix.lower()
    if kind == "supporting_document":
        if len(data) > MAX_SUPPORTING_BYTES:
            raise UploadValidationError("附件超过30MB限制")
        if extension == ".docx":
            validate_docx_upload(name, data)
            return ValidatedAttachment(extension, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        if (
            extension == ".pdf"
            and data.startswith(b"%PDF-")
            and b"%%EOF" in data[-2048:]
        ):
            return ValidatedAttachment(extension, "application/pdf")
        raise UploadValidationError("辅助资料目前仅支持有效的 DOCX 或 PDF")
    if kind == "site_image":
        if len(data) > MAX_IMAGE_BYTES:
            raise UploadValidationError("现场图片超过15MB限制")
        if extension in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff"):
            return ValidatedAttachment(extension, "image/jpeg")
        if extension == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ValidatedAttachment(extension, "image/png")
        raise UploadValidationError("现场图片目前仅支持有效的 JPG 或 PNG")
    raise UploadValidationError("未知附件类型")
