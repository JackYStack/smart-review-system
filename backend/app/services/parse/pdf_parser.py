from pydantic import BaseModel


class PdfRouteDecision(BaseModel):
    """PDF parsing route decision."""

    file_type: str
    enable_ocr: bool
    reason: str


def decide_pdf_route(has_text_layer: bool) -> PdfRouteDecision:
    """Choose a PDF parsing route from text-layer availability."""

    if has_text_layer:
        return PdfRouteDecision(
            file_type="text_pdf",
            enable_ocr=False,
            reason="text layer detected",
        )
    return PdfRouteDecision(file_type="scan_pdf", enable_ocr=True, reason="no text layer detected")
