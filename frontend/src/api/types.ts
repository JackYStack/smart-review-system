export type UserRole = 'user' | 'expert' | 'review_admin' | 'admin'

export interface UserPublic {
  id: number
  username: string
  phone: string
  role: UserRole
}

export interface UserListItem extends UserPublic {
  created_at: string | null
  updated_at: string | null
}

export interface KnowledgeBaseSettings {
  dify_base_url: string
  dify_dataset_name_prefix: string
  api_key_configured: boolean
}

export interface KnowledgeBaseTestResult {
  ok: boolean
  status: string
  detail: string
  latency_ms: number
  dataset_count: number
  datasets: DifyDatasetItem[]
}

export interface OnlyofficeSettings {
  docs_url: string
  callback_base_url: string
  editor_lang: string
  jwt_configured: boolean
}

export type ConfigSource = 'database' | 'environment' | 'default'
export type DifyOutputFormat = 'auto' | 'json' | 'markdown'
export type SchemeLifecycleStatus = 'draft' | 'pending_validation' | 'published' | 'disabled'
export type SchemeReadinessStatus = 'ready' | 'incomplete' | 'unavailable'

export interface WorkflowIntegrationSettings {
  enabled: boolean
  base_url: string
  api_key_configured: boolean
  user_prefix: string
  timeout_seconds: number
  output_variable: string
  output_format: DifyOutputFormat
  accept_partial: boolean
  continue_on_failure: boolean
  source: ConfigSource
}

export interface DocumentIntegrationSettings {
  paddleocr_api_url: string
  paddleocr_api_key_configured: boolean
  paddleocr_timeout_seconds: number
  convert_timeout_seconds: number
  libreoffice_configured: boolean
  source: ConfigSource
}

export interface IntegrationSettings {
  workflow: WorkflowIntegrationSettings
  document: DocumentIntegrationSettings
}

export interface SchemeWorkflowProfilePublic {
  scheme_type_id: number
  profile_id: number | null
  version: number | null
  configured: boolean
  source: 'scheme_profile' | 'global'
  enabled: boolean
  base_url: string
  api_key_configured: boolean
  user_prefix: string
  timeout_seconds: number
  output_variable: string
  output_format: DifyOutputFormat
  accept_partial: boolean
  continue_on_failure: boolean
  input_mapping: Record<string, string>
}

export interface SchemeWorkflowProfileUpdate {
  enabled: boolean
  base_url: string
  api_key?: string | null
  clear_api_key: boolean
  user_prefix: string
  timeout_seconds: number
  output_variable: string
  output_format: DifyOutputFormat
  accept_partial: boolean
  continue_on_failure: boolean
  input_mapping: Record<string, string>
}

export interface IntegrationTestResult {
  service: string
  ok: boolean
  status: string
  detail: string
  latency_ms?: number | null
  app_name?: string | null
}

export interface ServiceStatusItem {
  service: string
  label: string
  state: 'connected' | 'configured' | 'unconfigured' | 'error'
  detail: string
  editable: boolean
}

export interface ServiceStatus {
  services: ServiceStatusItem[]
}

export interface ConfigurationAudit {
  id: number
  section: string
  action: string
  actor_username: string
  changed_fields: string[]
  created_at: string | null
  can_rollback: boolean
}

export interface ConfigurationHistory {
  items: ConfigurationAudit[]
}

export interface OnlyofficeEditorConfigResponse {
  docs_url: string
  config: Record<string, unknown>
  token: string
}

export type LlmApiProtocol = 'openai_compatible' | 'anthropic'

export type ProviderId = 'volcengine' | 'minimax' | 'deepseek'

export interface VolcengineSettingsPart {
  api_protocol: 'openai_compatible'
  base_url: string
  endpoint_id: string
  api_key_configured: boolean
}

export interface MinimaxSettingsPart {
  api_protocol: 'anthropic'
  base_url: string
  model: string
  api_key_configured: boolean
}

export interface DeepseekSettingsPart {
  api_protocol: 'openai_compatible'
  base_url: string
  model: string
  api_key_configured: boolean
}

export interface ModelProviderSettings {
  default_provider: ProviderId | null
  volcengine: VolcengineSettingsPart
  minimax: MinimaxSettingsPart
  deepseek: DeepseekSettingsPart
}

export interface ModelTestResult {
  ok: boolean
  preview?: string | null
  error?: string | null
  latency_ms?: number | null
}

export interface DifyDatasetItem {
  id: string
  name: string
}

export type WorkflowStepId =
  | 'start'
  | 'structure'
  | 'compilation_basis'
  | 'context_consistency'
  | 'content'
  | 'full_document'
  | 'end'

export interface FullDocumentReviewConfig {
  review_prompt: string
  dify_dataset_id?: string | null
  knowledge_keywords?: string[]
}

export interface ReviewWorkflowData {
  steps: WorkflowStepId[]
}

export interface SchemeType {
  id: number
  category: string
  name: string
  remark: string | null
  lifecycle_status: SchemeLifecycleStatus
  published_at: string | null
  published_by_id: number | null
  published_template_version_id: number | null
  created_at: string | null
  updated_at: string | null
  /** 已解析且标题结构非空 */
  template_configured: boolean
  /** 已保存审核工作流 */
  workflow_configured: boolean
  /** 后端汇总的可提交状态；旧服务未返回时前端回退到模板/工作流状态判断 */
  readiness_status: SchemeReadinessStatus
  /** 尚未就绪的具体原因，例如模板、工作流、知识库或集成配置缺失 */
  readiness_issues: string[]
}

export interface BasisItem {
  id: number
  basis_id: string
  doc_type: string
  standard_no: string
  doc_name: string
  effect_status: string
  is_mandatory: boolean
  scheme_category: string
  scheme_name: string
  remark: string | null
  created_at: string | null
  updated_at: string | null
}

export type RuleType = 'required_section' | 'parameter_range' | 'cross_field' | 'formula'
export type RuleSeverity = 'error' | 'warning' | 'info'

/** 由确定性规则引擎执行的版本化规则。 */
export interface RuleDefinition {
  id: number
  scheme_type_id: number
  rule_code: string
  version: number
  name: string
  rule_type: RuleType
  severity: RuleSeverity
  enabled: boolean
  config: Record<string, unknown>
  source_standard_no: string
  source_standard_name: string
  source_version: string
  source_clause: string
  source_text: string
  created_by_id: number | null
  created_at: string
  updated_at: string
}

export interface FormulaDefinition {
  id: number
  rule_id: number
  formula_code: string
  version: number
  name: string
  expression: string
  variables: Record<string, Record<string, unknown> | string>
  result_unit: string
  comparator: '<' | '<=' | '==' | '>=' | '>' | '!='
  threshold_value: string | number | null
  threshold_parameter: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface TemplateNode {
  id: string
  level: number
  title: string
  content: string[]
  children: TemplateNode[]
  /** 引用同树中其他节点 id */
  ref_node_ids?: string[]
  /** 上下文一致性比对：与本章节对照校验的节点 id（用于发现跨章节语义冲突等） */
  context_consistency_ref_node_ids?: string[]
  /** 上下文一致性：描述比对重点与判定逻辑的补充提示词（可选） */
  context_consistency_prompt?: string
  /** 是否对该节点执行编制依据相关审核；缺省为 false（关闭） */
  compilation_basis_audit_enabled?: boolean
  /** Dify 知识库（数据集）id */
  dify_dataset_id?: string | null
  knowledge_keywords?: string[]
  review_prompt?: string
}

export interface TemplatePublic {
  id: number
  scheme_type_id: number
  minio_bucket: string
  object_key: string
  original_filename: string
  parsed_structure: { nodes: TemplateNode[] } | null
  review_workflow: ReviewWorkflowData | null
  full_document_review_config?: FullDocumentReviewConfig | null
  parsed_at: string | null
  updated_at: string | null
}

export type ReviewTaskStatus = 'pending' | 'processing' | 'succeeded' | 'failed' | 'canceled'

export interface ReportIssue {
  issue_id: string
  severity: string
  message: string
  evidence?: string
  anchor?: Record<string, unknown>
  related?: Record<string, unknown>
}

export interface ReportStep {
  step_id: string
  passed: boolean
  summary: string
  issues: ReportIssue[]
}

export interface ReviewReportV1 {
  version: 1
  steps: ReportStep[]
  generated_at?: string
  model_provider?: string | null
}

export interface ReviewTask {
  id: number
  scheme_type_id: number
  scheme_category: string
  scheme_name: string
  /** 管理员列表视图中返回提交人用户名 */
  owner_username?: string | null
  status: ReviewTaskStatus
  /** 审查业务结论；不得与任务技术执行状态混用 */
  review_conclusion?: string | null
  /** 报告完整性：完整、降级/部分完成或不可用 */
  completeness_status?: string | null
  /** 人工复核进度；旧任务可能没有该字段 */
  human_status?: string | null
  idempotency_key?: string | null
  priority: number
  attempt_no: number
  retry_of_task_id: number | null
  cancel_requested_at: string | null
  lease_expires_at?: string | null
  dify_workflow_profile_id?: number | null
  dify_workflow_profile_version?: number | null
  result_text: string | null
  error_message: string | null
  review_stage?: string | null
  /** 详情接口返回；列表通常不返回 */
  review_result_json?: string | null
  output_object_key?: string | null
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  input_tokens?: number | null
  output_tokens?: number | null
  total_tokens?: number | null
  /** 列表接口不返回；详情接口返回审核过程日志 */
  review_log?: string | null
  /** 调试开关开启后，仅详情接口返回拼接提示词 */
  debug_prompts?: DebugPromptItem[] | null
  original_filename: string
  created_at: string
  updated_at: string
}

/** 审核任务产生的不可变文档版本索引。 */
export interface DocumentArtifact {
  id: number
  task_id: number
  review_round_id: number | null
  artifact_kind: string
  version_no: number
  original_filename: string
  sha256: string
  size_bytes: number
  content_type: string
  immutable: boolean
  supersedes_artifact_id: number | null
  created_by_id: number | null
  created_at: string
}

export interface DownloadUrlResponse {
  url: string
  expires_seconds?: number
}

export interface DebugPromptItem {
  step_id: string
  template_node_id: string
  title_path: string[]
  prompt_text: string
  prompt_length: number
  created_at: string
}

export interface DashboardTaskByDay {
  date: string
  count: number
}

export interface DashboardTokenByDay {
  date: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

export interface DashboardTaskByStatus {
  status: string
  count: number
}

export interface DashboardTaskBySchemeType {
  scheme_type_id: number
  scheme_name: string
  scheme_category: string
  count: number
}

export interface DashboardDifyDataset {
  id: string
  name: string
  segment_count: number
  truncated: boolean
}

export interface DashboardDifyBlock {
  configured: boolean
  dataset_count: number
  segment_total: number
  datasets: DashboardDifyDataset[]
  error: string | null
  truncated: boolean
}

export interface DashboardSummary {
  refreshed_at: string | null
  users_total: number
  users_admin: number
  users_regular: number
  scheme_types_total: number
  templates_total: number
  basis_items_total: number
  review_tasks_total: number
  review_tasks_today: number
  active_submitters_7d: number
  completion_rate: number | null
  tokens_total_all: number
  input_tokens_total: number
  output_tokens_total: number
  tokens_today_total: number
  input_tokens_today: number
  output_tokens_today: number
  tokens_window_total: number
  input_tokens_window: number
  output_tokens_window: number
  tasks_per_day: DashboardTaskByDay[]
  tokens_per_day: DashboardTokenByDay[]
  tasks_by_status: DashboardTaskByStatus[]
  tasks_by_scheme_type: DashboardTaskBySchemeType[]
  dify: DashboardDifyBlock
}

export interface DashboardSettings {
  refresh_interval_minutes: number
}

export interface ReviewSettings {
  review_timeout_seconds: number
  prompt_debug_enabled: boolean
  worker_parallel_tasks: number
  compilation_basis_concurrency: number
  context_consistency_concurrency: number
  content_concurrency: number
  system_name: string
  logo_url: string | null
  favicon_url: string | null
  logo_configured: boolean
  favicon_configured: boolean
}

export interface PublicBrandingSettings {
  system_name: string
  logo_url: string | null
  favicon_url: string | null
  logo_configured: boolean
  favicon_configured: boolean
}

export type ReviewRoundStatus =
  | 'pending_ai'
  | 'pending'
  | 'in_review'
  | 'changes_requested'
  | 'pending_recheck'
  | 'approved'
  | 'signed'

export type IssueDisposition = 'pending' | 'accepted' | 'rejected' | 'modified' | 'resolved'

export type ExpertReviewConclusion =
  | 'passed'
  | 'conditional_pass'
  | 'changes_required'
  | 'rejected'

export interface ProjectPublic {
  id: number
  name: string
  region: string
  construction_unit: string
  contractor: string
  supervision_unit: string
  created_by_id: number | null
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  region: string
  construction_unit: string
  contractor: string
  supervision_unit: string
}

export interface DocumentRevisionPublic {
  id: number
  project_id: number
  scheme_type_id: number
  parent_revision_id: number | null
  version_label: string
  original_filename: string
  sha256: string
  created_by_id: number | null
  created_at: string
}

export interface RevisionTaskCreateResponse {
  revision: DocumentRevisionPublic
  task_id: number
  review_round_id: number
}

export interface ExpertReviewIssue {
  id: number
  review_round_id: number
  issue_key: string
  source_issue_id: string
  step_id: string
  severity: string
  message: string
  evidence: string
  anchor: Record<string, unknown>
  related: Record<string, unknown>
  disposition: IssueDisposition | string
  reviewer_comment: string
  final_severity: string | null
  reviewed_by_id: number | null
  reviewed_at: string | null
  created_at: string
  updated_at: string
}

export interface ExpertDecision {
  id: number
  action: string
  actor_id: number | null
  issue_id: number | null
  from_status: string | null
  to_status: string | null
  comment: string
  created_at: string
}

export interface ExpertReviewRound {
  id: number
  task_id: number
  document_revision_id: number | null
  project_id: number | null
  project_name: string
  project_region: string
  version_label: string
  parent_round_id: number | null
  round_no: number
  status: ReviewRoundStatus | string
  assigned_expert_id: number | null
  assigned_expert_username: string | null
  claimed_at: string | null
  claim_expires_at: string | null
  conclusion: ExpertReviewConclusion | string | null
  final_comment: string | null
  approved_at: string | null
  signed_by_id: number | null
  signed_at: string | null
  signed_report_available: boolean
  scheme_category: string
  scheme_name: string
  original_filename: string
  task_owner_username: string
  review_conclusion: string
  completeness_status: string
  issue_count: number
  pending_issue_count: number
  created_at: string
  updated_at: string
}

export interface ExpertReviewRoundDetail extends ExpertReviewRound {
  issues: ExpertReviewIssue[]
  decisions: ExpertDecision[]
}

export interface AuditEventPublic {
  id: number
  actor_id: number | null
  entity_type: string
  entity_id: string
  action: string
  data: Record<string, unknown>
  created_at: string
}

export interface SignedReportDownload {
  url: string
  sha256: string
  expires_seconds: number
}

export interface ReviewSourceDownload extends SignedReportDownload {
  filename: string
}
