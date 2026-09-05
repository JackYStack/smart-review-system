from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ReviewRoundStatus = Literal[
    "pending_ai",
    "pending",
    "in_review",
    "changes_requested",
    "pending_recheck",
    "approved",
    "signed",
]
IssueDisposition = Literal["pending", "accepted", "rejected", "modified", "resolved"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    region: str = Field(default="", max_length=255)
    construction_unit: str = Field(default="", max_length=255)
    contractor: str = Field(default="", max_length=255)
    supervision_unit: str = Field(default="", max_length=255)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    region: str | None = Field(default=None, max_length=255)
    construction_unit: str | None = Field(default=None, max_length=255)
    contractor: str | None = Field(default=None, max_length=255)
    supervision_unit: str | None = Field(default=None, max_length=255)


class ProjectPublic(BaseModel):
    id: int
    name: str
    region: str
    construction_unit: str
    contractor: str
    supervision_unit: str
    created_by_id: int | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentRevisionPublic(BaseModel):
    id: int
    project_id: int
    scheme_type_id: int
    parent_revision_id: int | None = None
    version_label: str
    original_filename: str
    sha256: str
    created_by_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewIssuePublic(BaseModel):
    id: int
    review_round_id: int
    issue_key: str
    source_issue_id: str
    step_id: str
    severity: str
    message: str
    evidence: str
    anchor: dict = Field(default_factory=dict)
    related: dict = Field(default_factory=dict)
    disposition: str
    reviewer_comment: str
    final_severity: str | None = None
    reviewed_by_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ExpertDecisionPublic(BaseModel):
    id: int
    action: str
    actor_id: int | None = None
    issue_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewRoundPublic(BaseModel):
    id: int
    task_id: int
    document_revision_id: int | None = None
    project_id: int | None = None
    project_name: str = ""
    project_region: str = ""
    version_label: str = ""
    parent_round_id: int | None = None
    round_no: int
    status: str
    assigned_expert_id: int | None = None
    assigned_expert_username: str | None = None
    claimed_at: datetime | None = None
    claim_expires_at: datetime | None = None
    conclusion: str | None = None
    final_comment: str | None = None
    approved_at: datetime | None = None
    signed_by_id: int | None = None
    signed_at: datetime | None = None
    signed_report_available: bool = False
    scheme_category: str = ""
    scheme_name: str = ""
    original_filename: str = ""
    task_owner_username: str = ""
    review_conclusion: str = "not_reviewed"
    completeness_status: str = "unavailable"
    issue_count: int = 0
    pending_issue_count: int = 0
    created_at: datetime
    updated_at: datetime


class ReviewRoundDetail(ReviewRoundPublic):
    issues: list[ReviewIssuePublic] = Field(default_factory=list)
    decisions: list[ExpertDecisionPublic] = Field(default_factory=list)


class IssueDecisionUpdate(BaseModel):
    disposition: IssueDisposition
    reviewer_comment: str = Field(default="", max_length=4000)
    final_severity: Literal["error", "warning", "info"] | None = None


class ReviewRoundAction(BaseModel):
    comment: str = Field(default="", max_length=8000)
    conclusion: Literal["passed", "conditional_pass", "changes_required", "rejected"] | None = None


class SignedReportDownload(BaseModel):
    url: str
    sha256: str
    expires_seconds: int = 3600


class ReviewSourceDownload(BaseModel):
    url: str
    sha256: str
    filename: str
    expires_seconds: int = 3600


class AuditEventPublic(BaseModel):
    id: int
    actor_id: int | None = None
    entity_type: str
    entity_id: str
    action: str
    data: dict = Field(default_factory=dict)
    created_at: datetime


class RevisionTaskCreateResponse(BaseModel):
    revision: DocumentRevisionPublic
    task_id: int
    review_round_id: int
