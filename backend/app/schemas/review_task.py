from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewTaskPublic(BaseModel):
    id: int
    scheme_type_id: int
    scheme_category: str = ""
    scheme_name: str = ""
    owner_username: str | None = Field(
        default=None,
        description="提交该任务的登录用户名；列表接口在管理员视图下返回",
    )
    status: str
    review_conclusion: str = "not_reviewed"
    completeness_status: str = "unavailable"
    human_status: str = "pending"
    idempotency_key: str | None = None
    priority: int = 0
    attempt_no: int = 1
    retry_of_task_id: int | None = None
    cancel_requested_at: datetime | None = None
    lease_expires_at: datetime | None = None
    dify_workflow_profile_id: int | None = None
    dify_workflow_profile_version: int | None = None
    dify_workflow_run_id: str | None = None
    dify_workflow_task_id: str | None = None
    dify_workflow_status: str | None = None
    dify_workflow_output_format: str | None = None
    result_text: str | None = None
    error_message: str | None = None
    review_stage: str | None = Field(default=None, description="处理中时的当前审核阶段 id")
    review_result_json: str | None = Field(
        default=None,
        description="统一审核报告 JSON；列表接口可为空以减负",
    )
    output_object_key: str | None = Field(default=None, description="带批注的 docx 对象键")
    started_at: datetime | None = Field(default=None, description="任务实际开始处理时间")
    finished_at: datetime | None = Field(default=None, description="任务处理结束时间（成功或失败）")
    duration_ms: int | None = Field(default=None, description="审核耗时（毫秒）")
    input_tokens: int | None = Field(default=None, description="词元输入量")
    output_tokens: int | None = Field(default=None, description="词元输出量")
    total_tokens: int | None = Field(default=None, description="词元总量")
    original_filename: str
    created_at: datetime
    updated_at: datetime
    review_log: str | None = Field(
        default=None,
        description="审核过程日志；列表接口为减轻负载不返回，仅详情接口返回",
    )
    debug_prompts: list["DebugPromptPublic"] | None = Field(
        default=None,
        description="调试开关开启后采集的拼接提示词，仅详情接口返回",
    )


class DebugPromptPublic(BaseModel):
    step_id: str
    template_node_id: str = ""
    title_path: list[str] = Field(default_factory=list)
    prompt_text: str
    prompt_length: int
    created_at: str


class ReviewTaskCreateResponse(BaseModel):
    task: ReviewTaskPublic
    message: str = Field(default="已提交审核任务")


class DocumentArtifactPublic(BaseModel):
    id: int
    task_id: int
    review_round_id: int | None = None
    artifact_kind: str
    version_no: int
    original_filename: str
    sha256: str
    size_bytes: int
    content_type: str
    immutable: bool
    supersedes_artifact_id: int | None = None
    created_by_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
