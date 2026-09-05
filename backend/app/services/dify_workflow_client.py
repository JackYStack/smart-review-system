"""Backend-only client for the team's Dify Workflow review application."""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
)


def _structured_evidence_text(value: Any) -> Any:
    """Accept Dify's useful structured evidence while storing readable text."""

    if isinstance(value, dict):
        lines = [
            f"{str(key).strip()}：{str(item).strip()}"
            for key, item in value.items()
            if str(item).strip()
        ]
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return value


class DifyWorkflowError(RuntimeError):
    """Raised when Dify cannot complete a workflow run."""

    def __init__(
        self,
        message: str,
        *,
        task_id: str = "",
        workflow_run_id: str = "",
        status: str = "",
        output_format: str = "",
    ) -> None:
        super().__init__(message)
        self.task_id = task_id
        self.workflow_run_id = workflow_run_id
        self.status = status
        self.output_format = output_format


class DifyReportIssue(BaseModel):
    """Published v3 Workflow issue contract."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["error", "warning", "info"]
    message: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    suggestions: list[str] = Field(..., min_length=1)
    title: str | None = None
    comparison: Literal["符合", "部分符合", "不符合", "资料不足"] | None = None
    regulation: str | None = None
    gap: str | None = None
    anchor: dict[str, Any] | None = None
    related: dict[str, Any] | None = None

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_structured_evidence(cls, value: Any) -> Any:
        return _structured_evidence_text(value)


class DifyCompliantItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    regulation: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_structured_evidence(cls, value: Any) -> Any:
        return _structured_evidence_text(value)


class DifyExtractedParameter(BaseModel):
    """Candidate engineering parameter extracted by the Workflow.

    The website deliberately records these as unverified LLM candidates.  The
    deterministic engine may calculate with them, but the evidence classifier
    will not label the result as a formal violation until an expert verifies
    both the value and its location.
    """

    model_config = ConfigDict(extra="forbid")

    parameter_name: str = Field(..., min_length=1, max_length=128)
    raw_value: str = Field(..., min_length=1, max_length=255)
    numeric_value: Decimal
    unit: str = Field(default="", max_length=32)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    source: dict[str, Any] = Field(..., min_length=1)


class DifyJsonReport(BaseModel):
    """Strict website/Dify JSON interchange schema."""

    model_config = ConfigDict(extra="forbid")

    passed: StrictBool
    summary: str = Field(..., min_length=1)
    issues: list[DifyReportIssue]
    compliant_items: list[DifyCompliantItem] | None = None
    parameters: list[DifyExtractedParameter] | None = None
    manual_checks: list[str] | None = None
    disclaimer: str | None = None


def validate_dify_report(
    report: str | dict[str, Any], configured_format: str
) -> tuple[str, str]:
    """Return normalized report text and detected format.

    JSON-looking output is never silently downgraded to text.  This prevents a
    malformed JSON contract from being presented as a successful review.
    """

    normalized_format = (configured_format or "auto").strip().lower()
    if normalized_format not in {"auto", "json", "markdown"}:
        raise DifyWorkflowError(f"Unsupported Dify output format: {configured_format}")
    if isinstance(report, dict):
        parsed: Any = report
        text = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(report or "").strip()
        cleaned = text
        if cleaned.startswith("```") and cleaned.endswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else cleaned
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = None

    if normalized_format == "markdown":
        if not text:
            raise DifyWorkflowError("Dify Workflow returned an empty Markdown report.")
        return text, "markdown"

    if parsed is not None:
        if not isinstance(parsed, dict):
            raise DifyWorkflowError("Dify JSON report must be an object.")
        try:
            validated = DifyJsonReport.model_validate(parsed)
        except ValidationError as exc:
            first = exc.errors(include_url=False)[0] if exc.errors() else {}
            location = ".".join(str(item) for item in first.get("loc", ())) or "report"
            message = str(first.get("msg") or "schema mismatch")
            raise DifyWorkflowError(
                f"Dify JSON report schema validation failed at {location}: {message}"
            ) from exc
        return (
            json.dumps(
                validated.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "json",
        )

    if normalized_format == "json" or text.lstrip().startswith(("{", "[")):
        raise DifyWorkflowError("Dify Workflow output is not valid JSON.")
    if not text:
        raise DifyWorkflowError("Dify Workflow returned an empty report.")
    detected = "markdown" if any(mark in text for mark in ("# ", "## ", "### ")) else "text"
    return text, detected


def _error_detail(response: httpx.Response) -> str:
    """Return a short server error without exposing credentials."""

    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:300] or "No response body"
    if isinstance(body, dict):
        for key in ("message", "detail", "code", "error"):
            value = body.get(key)
            if value:
                return str(value)[:300]
    return str(body)[:300]


@dataclass(frozen=True)
class DifyWorkflowResult:
    """Non-secret fields returned by a completed Dify workflow."""

    report: str
    task_id: str
    workflow_run_id: str
    status: str
    output_format: str


class DifyWorkflowClient:
    """Upload a scheme document and execute a published Dify Workflow."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 900,
        *,
        output_variable: str = "report",
        output_format: str = "auto",
        input_mapping: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = max(30, int(timeout_seconds))
        self.output_variable = output_variable.strip() or "report"
        self.output_format = (output_format or "auto").strip().lower()
        self.input_mapping = input_mapping or {
            "documents": "documents",
            "project_name": "project_name",
            "project_region": "project_region",
            "risk_type": "risk_type",
            "review_focus": "review_focus",
        }
        if not self.input_mapping.get("documents"):
            raise DifyWorkflowError("Dify input mapping must include documents.")
        self.transport = transport

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def run_review(
        self,
        *,
        file_name: str,
        file_content: bytes,
        project_name: str,
        project_region: str,
        risk_type: str,
        review_focus: str,
        user: str,
        document_files: list[tuple[str, bytes]] | None = None,
        site_image_files: list[tuple[str, bytes]] | None = None,
    ) -> DifyWorkflowResult:
        if not self.base_url:
            raise DifyWorkflowError("Dify Workflow API URL is not configured.")
        if not self.api_key:
            raise DifyWorkflowError("Dify Workflow API key is not configured.")

        timeout = httpx.Timeout(
            connect=20.0,
            read=float(self.timeout_seconds),
            write=120.0,
            pool=20.0,
        )
        try:
            with httpx.Client(timeout=timeout, transport=self.transport) as client:
                documents_to_upload = document_files or [(file_name, file_content)]
                document_inputs = [
                    {
                        "type": "document",
                        "transfer_method": "local_file",
                        "upload_file_id": self._upload_file(
                            client, item_name, item_content, user
                        ),
                    }
                    for item_name, item_content in documents_to_upload
                ]
                image_inputs = [
                    {
                        "type": "image",
                        "transfer_method": "local_file",
                        "upload_file_id": self._upload_file(
                            client, item_name, item_content, user
                        ),
                    }
                    for item_name, item_content in (site_image_files or [])
                ]
                canonical_inputs: dict[str, Any] = {
                    "documents": document_inputs,
                    "site_images": image_inputs,
                    "project_name": project_name,
                    "project_region": project_region,
                    "risk_type": risk_type,
                    "review_focus": review_focus,
                }
                mapped_inputs = {
                    target: canonical_inputs[source]
                    for source, target in self.input_mapping.items()
                    if source in canonical_inputs and target
                }
                payload: dict[str, Any] = {
                    "inputs": mapped_inputs,
                    # SSE keep-alive events prevent long reviews from looking idle.
                    "response_mode": "streaming",
                    "user": user,
                }
                return self._stream_workflow(client, payload)
        except DifyWorkflowError:
            raise
        except httpx.TimeoutException as exc:
            raise DifyWorkflowError(
                f"Dify Workflow timed out after {self.timeout_seconds} seconds "
                f"({type(exc).__name__})."
            ) from exc
        except httpx.RequestError as exc:
            detail = str(exc) or repr(exc)
            raise DifyWorkflowError(
                f"Dify Workflow network request failed ({type(exc).__name__}): {detail}"
            ) from exc

    def _upload_file(
        self,
        client: httpx.Client,
        file_name: str,
        file_content: bytes,
        user: str,
    ) -> str:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        response = client.post(
            f"{self.base_url}/files/upload",
            headers=self._headers,
            data={"user": user},
            files={"file": (file_name, file_content, mime_type)},
        )
        if response.is_error:
            raise DifyWorkflowError(
                f"Dify file upload returned HTTP {response.status_code}: "
                f"{_error_detail(response)}"
            )
        upload_id = response.json().get("id")
        if not isinstance(upload_id, str) or not upload_id:
            raise DifyWorkflowError("Dify file upload did not return an id.")
        return upload_id

    def _stream_workflow(
        self,
        client: httpx.Client,
        payload: dict[str, Any],
    ) -> DifyWorkflowResult:
        task_id = ""
        workflow_run_id = ""
        with client.stream(
            "POST",
            f"{self.base_url}/workflows/run",
            headers={**self._headers, "Content-Type": "application/json"},
            json=payload,
        ) as response:
            if response.is_error:
                response.read()
                raise DifyWorkflowError(
                    f"Dify Workflow returned HTTP {response.status_code}: "
                    f"{_error_detail(response)}"
                )
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line.removeprefix("data:").strip())
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                task_id = str(event.get("task_id") or task_id)
                workflow_run_id = str(event.get("workflow_run_id") or workflow_run_id)
                event_type = event.get("event")
                data = event.get("data") or {}
                if event_type == "workflow_failed":
                    message = data.get("error") or "Unknown workflow error"
                    raise DifyWorkflowError(
                        f"Dify Workflow failed: {message}",
                        task_id=task_id,
                        workflow_run_id=workflow_run_id,
                        status=str(data.get("status") or "failed"),
                        output_format=self.output_format,
                    )
                if event_type != "workflow_finished":
                    continue
                status = str(data.get("status") or "unknown")
                report = (data.get("outputs") or {}).get(self.output_variable)
                report_missing = report is None or (
                    isinstance(report, str) and not report.strip()
                )
                if (
                    report_missing
                    and status == "partial-succeeded"
                    and workflow_run_id
                ):
                    detail_response = client.get(
                        f"{self.base_url}/workflows/run/{workflow_run_id}",
                        headers=self._headers,
                    )
                    if detail_response.is_success:
                        report = (detail_response.json().get("outputs") or {}).get(
                            self.output_variable
                        )
                if status not in ("succeeded", "partial-succeeded"):
                    message = data.get("error") or f"status={status}"
                    raise DifyWorkflowError(
                        f"Dify Workflow did not succeed: {message}",
                        task_id=task_id,
                        workflow_run_id=workflow_run_id,
                        status=status,
                        output_format=self.output_format,
                    )
                if not isinstance(report, (str, dict)) or not report:
                    raise DifyWorkflowError(
                        "Dify Workflow completed without the required "
                        f"'{self.output_variable}' output "
                        f"(status={status})."
                    )
                try:
                    normalized_report, detected_format = validate_dify_report(
                        report, self.output_format
                    )
                except DifyWorkflowError as exc:
                    raise DifyWorkflowError(
                        str(exc),
                        task_id=task_id,
                        workflow_run_id=workflow_run_id,
                        status=status,
                        output_format=self.output_format,
                    ) from exc
                return DifyWorkflowResult(
                    report=normalized_report,
                    task_id=task_id,
                    workflow_run_id=workflow_run_id,
                    status=status,
                    output_format=detected_format,
                )
        raise DifyWorkflowError(
            "Dify Workflow streaming ended before workflow_finished was received.",
            task_id=task_id,
            workflow_run_id=workflow_run_id,
            status="stream-ended",
            output_format=self.output_format,
        )
