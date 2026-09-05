from __future__ import annotations

import pytest

from app.services.attachment_validation import validate_supporting_attachment
from app.services.upload_validation import UploadValidationError


def test_minimal_pdf_requires_header_and_eof_marker() -> None:
    result = validate_supporting_attachment(
        "calculation.pdf",
        b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
        kind="supporting_document",
    )
    assert result.content_type == "application/pdf"


def test_pdf_header_alone_is_not_accepted() -> None:
    with pytest.raises(UploadValidationError, match="DOCX 或 PDF"):
        validate_supporting_attachment(
            "fake.pdf",
            b"%PDF-this-is-not-a-complete-file",
            kind="supporting_document",
        )


@pytest.mark.parametrize(
    ("filename", "payload", "content_type"),
    [
        ("site.jpg", b"\xff\xd8\xff\xe0payload", "image/jpeg"),
        ("site.png", b"\x89PNG\r\n\x1a\npayload", "image/png"),
    ],
)
def test_supported_image_signatures(filename: str, payload: bytes, content_type: str) -> None:
    result = validate_supporting_attachment(filename, payload, kind="site_image")
    assert result.content_type == content_type
