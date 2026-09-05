"""PaddleOCR PP-StructureV3 backed document parser.

PaddleOCR is the source of headings, paragraphs, tables and formulas. DOCX
files are first rendered to PDF because the official serving API accepts PDF
or image input. The DOCX is inspected only to map headings back to paragraph
indices for Word comments.
"""

from __future__ import annotations

import base64
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
from docx import Document

from app.config import get_settings
from app.services.integration_settings import EffectiveDocumentIntegration


class PaddleDocumentParseError(RuntimeError):
    """Raised when Paddle cannot produce a usable structured document."""


_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,9})\s+(.+?)\s*$")
_CHAPTER_HEADING_RE = re.compile(r"^(?P<marker>第[一二三四五六七八九十百0-9]+章)\s*(?P<title>.+)$")
_CN_NUMBER_HEADING_RE = re.compile(
    r"^(?P<marker>[（(]?[一二三四五六七八九十]+[）)、])\s*(?P<title>.+)$"
)
_DECIMAL_HEADING_RE = re.compile(
    r"^(?P<marker>\d+(?:\.\d+)*(?:[.、])?)\s+(?P<title>.+)$"
)


def _plain_heading(line: str) -> tuple[int, str] | None:
    """Recognise numbered Chinese headings when Paddle did not emit Markdown."""

    chapter = _CHAPTER_HEADING_RE.match(line)
    if chapter:
        return 1, line
    chinese_number = _CN_NUMBER_HEADING_RE.match(line)
    if chinese_number:
        marker = chinese_number.group("marker")
        return (2 if marker.startswith(("（", "(")) else 1), line
    decimal = _DECIMAL_HEADING_RE.match(line)
    if decimal:
        marker = decimal.group("marker").rstrip(".、")
        return min(marker.count(".") + 1, 9), line
    return None


def _normalized_title(value: str) -> str:
    return re.sub(r"[\s　:：,，.。;；、()（）【】\[\]]+", "", value or "").lower()


def _docx_heading_anchors(docx_bytes: bytes) -> list[tuple[int, str]]:
    """Return Word paragraph positions solely for later comment anchoring."""

    document = Document(io.BytesIO(docx_bytes))
    anchors: list[tuple[int, str]] = []
    for index, paragraph in enumerate(document.paragraphs):
        text = (paragraph.text or "").strip()
        style = paragraph.style.name if paragraph.style else ""
        is_heading_style = re.match(r"(?:Heading|标题)\s*\d+", style, re.I)
        if text and (is_heading_style or _plain_heading(text)):
            anchors.append((index, text))
    return anchors


def _match_heading_anchor(
    title: str,
    anchors: list[tuple[int, str]],
    used: set[int],
) -> int | None:
    wanted = _normalized_title(title)
    if not wanted:
        return None
    for index, candidate in anchors:
        if index in used:
            continue
        actual = _normalized_title(candidate)
        if wanted == actual or wanted in actual or actual in wanted:
            used.add(index)
            return index
    return None


def markdown_to_tree(markdown: str, *, docx_bytes: bytes | None = None) -> dict[str, Any]:
    """Convert Paddle's ordered Markdown into SmartReview's heading tree."""

    anchors = _docx_heading_anchors(docx_bytes) if docx_bytes else []
    used_anchors: set[int] = set()
    roots: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []
    counter = 0

    def new_node(level: int, title: str) -> dict[str, Any]:
        nonlocal counter
        counter += 1
        return {
            "id": f"n{counter}",
            "level": level,
            "title": title.strip(),
            "heading_para_index": _match_heading_anchor(title, anchors, used_anchors),
            "content": [],
            "children": [],
        }

    for raw_line in (markdown or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _MARKDOWN_HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
        else:
            numbered = _plain_heading(line)
            if numbered and len(line) <= 80:
                level, _ = numbered
                title = line
            else:
                if not stack:
                    if not roots:
                        roots.append(new_node(1, "文档正文"))
                    stack[:] = [roots[-1]]
                stack[-1]["content"].append(line)
                continue

        while stack and int(stack[-1]["level"]) >= level:
            stack.pop()
        node = new_node(level, title)
        if stack:
            stack[-1]["children"].append(node)
        else:
            roots.append(node)
        stack.append(node)

    if not roots:
        raise PaddleDocumentParseError("PaddleOCR 返回了空文档，无法生成标题树。")
    return {"nodes": roots}


def _docx_to_pdf(
    docx_bytes: bytes,
    runtime: EffectiveDocumentIntegration | None = None,
) -> bytes:
    settings = get_settings()
    configured = (runtime.libreoffice_bin if runtime else settings.libreoffice_bin).strip()
    executable = configured or shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        raise PaddleDocumentParseError(
            "DOCX 送入 PaddleOCR 前需要 LibreOffice 转为 PDF；未找到 soffice。"
        )
    with tempfile.TemporaryDirectory(prefix="smartreview-paddle-") as temp_dir:
        temp_path = Path(temp_dir)
        source = temp_path / "source.docx"
        source.write_bytes(docx_bytes)
        process = subprocess.run(
            [
                executable,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_path),
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=(
                runtime.convert_timeout_seconds
                if runtime
                else settings.paddle_convert_timeout_seconds
            ),
            check=False,
        )
        pdf_path = temp_path / "source.pdf"
        if process.returncode != 0 or not pdf_path.is_file():
            detail = (process.stderr or process.stdout or "转换未生成 PDF").strip()[-500:]
            raise PaddleDocumentParseError(f"DOCX 转 PDF 失败：{detail}")
        return pdf_path.read_bytes()


def _request_paddle(
    pdf_bytes: bytes,
    runtime: EffectiveDocumentIntegration | None = None,
) -> str:
    settings = get_settings()
    url = (
        runtime.paddleocr_api_url if runtime else settings.paddleocr_api_url
    ).strip()
    if not url:
        raise PaddleDocumentParseError("尚未配置 PADDLEOCR_API_URL。")
    headers = {"Content-Type": "application/json"}
    api_key = runtime.paddleocr_api_key if runtime else settings.paddleocr_api_key
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    payload = {
        "file": base64.b64encode(pdf_bytes).decode("ascii"),
        "fileType": 0,
        "useDocOrientationClassify": True,
        "useDocUnwarping": False,
        "useTextlineOrientation": True,
        # The deployed PP-StructureV3 pipeline does not initialise the optional
        # seal model.  Enabling it makes every document fail before layout and
        # text parsing can start.
        "useSealRecognition": False,
        "useTableRecognition": True,
        "useFormulaRecognition": True,
        "prettifyMarkdown": True,
        "returnMarkdownImages": False,
        "visualize": False,
    }
    try:
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=(
                runtime.paddleocr_timeout_seconds
                if runtime
                else settings.paddleocr_timeout_seconds
            ),
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PaddleDocumentParseError(f"PaddleOCR 服务调用失败：{exc}") from exc
    if body.get("errorCode") not in (None, 0):
        raise PaddleDocumentParseError(
            f"PaddleOCR 返回错误：{body.get('errorMsg') or body.get('errorCode')}"
        )
    results = ((body.get("result") or {}).get("layoutParsingResults") or [])
    markdown_pages = [
        str((item.get("markdown") or {}).get("text") or "").strip()
        for item in results
        if isinstance(item, dict)
    ]
    markdown = "\n\n".join(page for page in markdown_pages if page)
    if not markdown:
        raise PaddleDocumentParseError("PaddleOCR 未返回可用的 Markdown 文本。")
    return markdown


def parse_docx_to_tree_with_paddle(
    docx_bytes: bytes,
    *,
    paragraph_image_keys: dict[int, list[str]] | None = None,
    runtime: EffectiveDocumentIntegration | None = None,
) -> dict[str, Any]:
    """Parse a DOCX through PaddleOCR and return SmartReview's tree schema."""

    pdf_bytes = _docx_to_pdf(docx_bytes, runtime)
    markdown = _request_paddle(pdf_bytes, runtime)
    tree = markdown_to_tree(markdown, docx_bytes=docx_bytes)
    tree["parser"] = {
        "engine": "PaddleOCR PP-StructureV3",
        "source_format": "docx",
        "intermediate_format": "pdf",
    }
    if paragraph_image_keys:
        tree["source_image_count"] = sum(len(items) for items in paragraph_image_keys.values())
    return tree


def tree_to_json_str(tree: dict[str, Any]) -> str:
    return json.dumps(tree, ensure_ascii=False)
