import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type {
  AuditEventPublic,
  BasisItem,
  ConfigurationHistory,
  DashboardSettings,
  ExpertReviewIssue,
  ExpertReviewRoundDetail,
  FormulaDefinition,
  IntegrationSettings,
  KnowledgeBaseSettings,
  ModelProviderSettings,
  OnlyofficeSettings,
  ProjectPublic,
  ReviewReportV1,
  ReviewSettings,
  ReviewTask,
  RuleDefinition,
  SchemeType,
  SchemeWorkflowProfilePublic,
  TemplatePublic,
  UserListItem,
} from '../api/types'

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

type RuntimeDemoConfig = {
  scheme_types?: Array<Partial<SchemeType> & { id: number; category: string; name: string }>
  projects?: Array<Partial<ProjectPublic> & { id: number; name: string }>
  basis?: Array<Partial<BasisItem>>
  settings_example?: {
    paddleocr_api_url?: string
    workflow_output_variable?: string
    workflow_output_format?: 'auto' | 'json' | 'markdown'
    workflow_timeout_seconds?: number
    onlyoffice_docs_url?: string
  }
}

let schemes: SchemeType[] = [
  {
    id: 1,
    category: '脚手架工程',
    name: '落地式钢管脚手架专项施工方案',
    remark: '本地演示类型',
    lifecycle_status: 'published',
    published_at: '2026-08-23T23:00:00+08:00',
    published_by_id: 1,
    published_template_version_id: 1,
    created_at: '2026-08-23T23:00:00+08:00',
    updated_at: '2026-08-23T23:00:00+08:00',
    template_configured: true,
    workflow_configured: true,
    readiness_status: 'ready',
    readiness_issues: [],
  },
  {
    id: 2,
    category: '模板工程及支撑体系',
    name: '高大模板专项施工方案',
    remark: '本地演示类型',
    lifecycle_status: 'published',
    published_at: '2026-08-23T23:00:00+08:00',
    published_by_id: 1,
    published_template_version_id: 2,
    created_at: '2026-08-23T23:00:00+08:00',
    updated_at: '2026-08-23T23:00:00+08:00',
    template_configured: true,
    workflow_configured: true,
    readiness_status: 'ready',
    readiness_issues: [],
  },
]

const demoNow = '2026-08-24T09:00:00+08:00'

let basisItems: BasisItem[] = [
  {
    id: 1,
    basis_id: 'BASIS-SCAFFOLD-001',
    doc_type: '行业标准',
    standard_no: 'JGJ 130-2011',
    doc_name: '建筑施工扣件式钢管脚手架安全技术规范',
    effect_status: '现行（演示，正式使用前须由法规人员核验）',
    is_mandatory: true,
    scheme_category: '脚手架工程',
    scheme_name: '落地式钢管脚手架专项施工方案',
    remark: '离线演示依据，展示法规证据链和规则关联。',
    created_at: demoNow,
    updated_at: demoNow,
  },
  {
    id: 2,
    basis_id: 'BASIS-MANAGEMENT-001',
    doc_type: '部门规章',
    standard_no: '住建部令第37号',
    doc_name: '危险性较大的分部分项工程安全管理规定',
    effect_status: '现行（演示）',
    is_mandatory: true,
    scheme_category: '脚手架工程',
    scheme_name: '落地式钢管脚手架专项施工方案',
    remark: '用于演示危大工程专项方案程序性检查。',
    created_at: demoNow,
    updated_at: demoNow,
  },
]

const templateNodes = [
  {
    id: 'root', level: 1, title: '落地式钢管脚手架专项施工方案', content: [],
    compilation_basis_audit_enabled: true,
    review_prompt: '检查方案总体完整性、程序合规性和关键参数。',
    knowledge_keywords: ['脚手架', '危大工程'],
    children: [
      { id: 'overview', level: 2, title: '一、工程概况', content: ['工程位置、架体高度、基础条件与周边环境。'], children: [], review_prompt: '核对工程概况、架体形式、高度、荷载和基础条件。', context_consistency_ref_node_ids: ['design'] },
      { id: 'basis', level: 2, title: '二、编制依据', content: ['列明适用法规、规范及有效版本。'], children: [], compilation_basis_audit_enabled: true, dify_dataset_id: 'demo-scaffold-standards', knowledge_keywords: ['JGJ 130', '危大工程'] },
      { id: 'design', level: 2, title: '三、设计与构造', content: ['立杆、横杆、剪刀撑、连墙件和基础参数。'], children: [], review_prompt: '检查构造参数、连墙件布置及跨章节一致性。', context_consistency_ref_node_ids: ['overview', 'calculation'] },
      { id: 'construction', level: 2, title: '四、施工工艺与验收', content: ['搭设、拆除、验收和使用管理。'], children: [], review_prompt: '检查施工顺序、验收程序、人员职责和现场可执行性。' },
      { id: 'monitoring', level: 2, title: '五、监测与应急处置', content: ['监测项目、频率、预警值、响应流程和撤离路线。'], children: [], review_prompt: '检查监测指标、预警阈值和应急处置闭环。' },
      { id: 'calculation', level: 2, title: '六、计算书', content: ['荷载、构件承载力和稳定性验算。'], children: [], review_prompt: '提取计算参数并交由确定性公式引擎复核。', context_consistency_ref_node_ids: ['design'] },
    ],
  },
]

const templates = new Map<number, TemplatePublic>([
  [1, {
    id: 1,
    scheme_type_id: 1,
    minio_bucket: 'smart-review-demo',
    object_key: 'templates/scaffold-demo-template.docx',
    original_filename: '落地式钢管脚手架专项施工方案_标准模板.docx',
    parsed_structure: { nodes: templateNodes },
    review_workflow: { steps: ['start', 'structure', 'compilation_basis', 'context_consistency', 'content', 'full_document', 'end'] },
    full_document_review_config: {
      review_prompt: '通篇检查章节完整性、关键参数一致性、危险源控制、验收、监测、应急和法规依据。',
      dify_dataset_id: 'demo-scaffold-standards',
      knowledge_keywords: ['脚手架', '连墙件', '验收', '监测'],
    },
    parsed_at: demoNow,
    updated_at: demoNow,
  }],
  [2, {
    id: 2,
    scheme_type_id: 2,
    minio_bucket: 'smart-review-demo',
    object_key: 'templates/formwork-demo-template.docx',
    original_filename: '高大模板专项施工方案_标准模板.docx',
    parsed_structure: { nodes: [{ id: 'formwork-root', level: 1, title: '高大模板专项施工方案', content: [], children: [] }] },
    review_workflow: { steps: ['start', 'structure', 'content', 'full_document', 'end'] },
    full_document_review_config: { review_prompt: '演示：检查高大模板支撑体系、荷载和验收。', dify_dataset_id: null, knowledge_keywords: ['高大模板', '支撑体系'] },
    parsed_at: demoNow,
    updated_at: demoNow,
  }],
])
let projects: ProjectPublic[] = [
  {
    id: 1,
    name: '城市更新脚手架工程（演示）',
    region: '北京市海淀区',
    construction_unit: '演示建设单位',
    contractor: '演示施工单位',
    supervision_unit: '演示监理单位',
    created_by_id: 1,
    archived_at: null,
    created_at: demoNow,
    updated_at: demoNow,
  },
]

const schemeProfiles = new Map<number, SchemeWorkflowProfilePublic>()

let rules: RuleDefinition[] = [
  {
    id: 1,
    scheme_type_id: 1,
    rule_code: 'SCAFFOLD-STRUCT-001',
    version: 1,
    name: '施工监测章节完整性',
    rule_type: 'required_section',
    severity: 'error',
    enabled: true,
    config: { keywords: ['施工监测', '监测预警'], match: 'all' },
    source_standard_no: 'JGJ 130-2011',
    source_standard_name: '建筑施工扣件式钢管脚手架安全技术规范',
    source_version: '2011',
    source_clause: '8.2.3',
    source_text: '脚手架使用中，应定期检查相关安全状态并形成记录。',
    created_by_id: 1,
    created_at: demoNow,
    updated_at: demoNow,
  },
  {
    id: 2,
    scheme_type_id: 1,
    rule_code: 'SCAFFOLD-HEIGHT-001',
    version: 1,
    name: '架体搭设高度范围',
    rule_type: 'parameter_range',
    severity: 'warning',
    enabled: true,
    config: { parameter: 'scaffold_height', min: 0, max: 50, unit: 'm' },
    source_standard_no: 'JGJ 130-2011',
    source_standard_name: '建筑施工扣件式钢管脚手架安全技术规范',
    source_version: '2011',
    source_clause: '1.0.2',
    source_text: '本规范适用于建筑施工用落地式单、双排扣件式钢管脚手架的设计、施工及验收。',
    created_by_id: 1,
    created_at: demoNow,
    updated_at: demoNow,
  },
  {
    id: 3,
    scheme_type_id: 1,
    rule_code: 'SCAFFOLD-LOAD-001',
    version: 1,
    name: '构件承载力复核',
    rule_type: 'formula',
    severity: 'error',
    enabled: true,
    config: {},
    source_standard_no: 'JGJ 130-2011',
    source_standard_name: '建筑施工扣件式钢管脚手架安全技术规范',
    source_version: '2011',
    source_clause: '5.2.1',
    source_text: '纵向、横向水平杆等受弯构件的强度和连接扣件的抗滑承载力应按规定计算。',
    created_by_id: 1,
    created_at: demoNow,
    updated_at: demoNow,
  },
]

let formulas: FormulaDefinition[] = [
  {
    id: 1,
    rule_id: 3,
    formula_code: 'SCAFFOLD-LOAD-CHECK-001',
    version: 1,
    name: '荷载效应与承载力比值',
    expression: 'design_load / capacity',
    variables: {
      design_load: { parameter: 'design_load', unit: 'kN' },
      capacity: { parameter: 'member_capacity', unit: 'kN' },
    },
    result_unit: '',
    comparator: '<=',
    threshold_value: '1',
    threshold_parameter: null,
    enabled: true,
    created_at: demoNow,
    updated_at: demoNow,
  },
]

function inheritedProfile(schemeTypeId: number): SchemeWorkflowProfilePublic {
  return {
    scheme_type_id: schemeTypeId,
    profile_id: null,
    version: null,
    configured: false,
    source: 'global',
    enabled: true,
    base_url: 'http://100.72.36.25/v1',
    api_key_configured: true,
    user_prefix: 'smart-review',
    timeout_seconds: 900,
    output_variable: 'report',
    output_format: 'json',
    accept_partial: true,
    continue_on_failure: true,
    input_mapping: {
      documents: 'documents',
      site_images: 'site_images',
      project_name: 'project_name',
      project_region: 'project_region',
      risk_type: 'risk_type',
      review_focus: 'review_focus',
    },
  }
}

function makeReport(): ReviewReportV1 {
  return {
    version: 1,
    generated_at: new Date().toISOString(),
    model_provider: 'Dify Workflow（演示数据）',
    steps: [
      {
        step_id: 'structure',
        passed: false,
        summary: '章节结构检查完成，发现2项待补充内容。',
        issues: [
          {
            issue_id: 'demo-structure-1',
            severity: 'warning',
            message: '缺少施工监测专项章节',
            evidence: '当前方案目录未检出“施工监测”或等效章节。',
            anchor: { title_path: ['施工方案'] },
            related: { suggestions: ['补充监测项目、监测频率、预警值和责任人。'] },
          },
          {
            issue_id: 'demo-structure-2',
            severity: 'warning',
            message: '应急处置内容不完整',
            evidence: '应急预案仅列出联系电话，未见响应流程和现场处置措施。',
            anchor: { title_path: ['应急预案'] },
            related: { suggestions: ['补充险情分级、响应程序、撤离路线和救援资源。'] },
          },
        ],
      },
      {
        step_id: 'dify_workflow',
        passed: false,
        summary: '脚手架方案模拟审查完成，发现3项关键问题。',
        issues: [
          {
            issue_id: 'demo-dify-1',
            severity: 'error',
            message: '连墙件布置间距与方案控制要求不一致',
            evidence: '方案写明“连墙件按三步三跨布置”，但计算与构造说明采用更严格的两步三跨控制。',
            related: {
              suggestions: ['统一方案正文、计算书和节点图中的连墙件布置参数，并重新复核架体稳定性。'],
              standard_no: 'JGJ 130',
            },
          },
          {
            issue_id: 'demo-dify-2',
            severity: 'error',
            message: '立杆基础处理缺少承载力验算依据',
            evidence: '方案仅写“地面夯实后设置垫板”，未提供地基承载力取值、排水措施及沉降控制要求。',
            related: {
              suggestions: ['补充地基承载力参数、垫板规格、排水做法和沉降巡查要求。'],
            },
          },
          {
            issue_id: 'demo-dify-3',
            severity: 'warning',
            message: '卸料平台荷载控制措施不具备现场可执行性',
            evidence: '方案规定“严禁超载”，但未给出限载值、标识设置和材料堆放控制方式。',
            related: {
              suggestions: ['明确允许荷载、悬挂限载牌，并制定材料分类堆放和巡查记录要求。'],
            },
          },
        ],
      },
    ],
  }
}

function createTask(id: number, filename: string, schemeId = 1): ReviewTask {
  const scheme = schemes.find((item) => item.id === schemeId) ?? schemes[0]
  const now = new Date().toISOString()
  return {
    id,
    scheme_type_id: scheme.id,
    scheme_category: scheme.category,
    scheme_name: scheme.name,
    owner_username: '演示管理员',
    status: 'succeeded',
    review_conclusion: 'changes_required',
    completeness_status: 'complete',
    human_status: 'pending',
    priority: 0,
    attempt_no: 1,
    retry_of_task_id: null,
    cancel_requested_at: null,
    result_text: '模拟审核完成',
    error_message: null,
    review_result_json: JSON.stringify(makeReport()),
    output_object_key: 'demo/annotated.docx',
    started_at: now,
    finished_at: now,
    duration_ms: 4280,
    input_tokens: 3560,
    output_tokens: 1260,
    total_tokens: 4820,
    review_log:
      '[演示] PaddleOCR文档解析完成\n[演示] 结构审核完成\n[演示] RAGFlow法规检索完成\n[演示] Dify Workflow结构化审查完成',
    debug_prompts: [],
    original_filename: filename,
    created_at: now,
    updated_at: now,
  }
}

const pendingDemoTask = createTask(1002, '演示待取消任务.docx')
pendingDemoTask.status = 'pending'
pendingDemoTask.result_text = null
pendingDemoTask.output_object_key = null
pendingDemoTask.finished_at = null
pendingDemoTask.duration_ms = null
pendingDemoTask.review_conclusion = 'not_reviewed'
pendingDemoTask.completeness_status = 'unavailable'

let tasks: ReviewTask[] = [
  createTask(1001, '演示用_落地式脚手架专项方案_含缺陷.docx'),
  pendingDemoTask,
]

let users: UserListItem[] = [
  { id: 1, username: '演示管理员', phone: 'demo-admin', role: 'admin', created_at: demoNow, updated_at: demoNow },
  { id: 2, username: '张专家（演示）', phone: 'demo-expert', role: 'expert', created_at: demoNow, updated_at: demoNow },
  { id: 3, username: '项目提交人（演示）', phone: 'demo-user', role: 'user', created_at: demoNow, updated_at: demoNow },
]

let knowledgeBaseSettings: KnowledgeBaseSettings = {
  dify_base_url: 'http://100.72.36.25/v1',
  dify_dataset_name_prefix: '危大工程-',
  api_key_configured: true,
}

let modelProviderSettings: ModelProviderSettings = {
  default_provider: 'deepseek',
  volcengine: { api_protocol: 'openai_compatible', base_url: 'https://ark.cn-beijing.volces.com/api/v3', endpoint_id: '演示端点', api_key_configured: false },
  minimax: { api_protocol: 'anthropic', base_url: 'https://api.minimax.chat', model: 'MiniMax-M2', api_key_configured: false },
  deepseek: { api_protocol: 'openai_compatible', base_url: 'https://api.deepseek.com', model: 'deepseek-chat', api_key_configured: true },
}

let onlyofficeSettings: OnlyofficeSettings = {
  docs_url: 'http://127.0.0.1:8080',
  callback_base_url: 'http://backend:8000',
  editor_lang: 'zh',
  jwt_configured: true,
}

let dashboardSettings: DashboardSettings = { refresh_interval_minutes: 5 }

let reviewSettings: ReviewSettings = {
  review_timeout_seconds: 900,
  prompt_debug_enabled: false,
  worker_parallel_tasks: 1,
  compilation_basis_concurrency: 1,
  context_consistency_concurrency: 1,
  content_concurrency: 1,
  system_name: '筑安智审—危大工程专项方案智能审查系统（完整离线范例）',
  logo_url: null,
  favicon_url: null,
  logo_configured: false,
  favicon_configured: false,
}

let integrationSettings: IntegrationSettings = {
  workflow: {
    enabled: true,
    base_url: 'http://100.72.36.25/v1',
    api_key_configured: true,
    user_prefix: 'smart-review',
    timeout_seconds: 900,
    output_variable: 'report',
    output_format: 'json',
    accept_partial: true,
    continue_on_failure: true,
    source: 'database',
  },
  document: {
    paddleocr_api_url: 'http://paddleocr:8866',
    paddleocr_api_key_configured: true,
    paddleocr_timeout_seconds: 900,
    convert_timeout_seconds: 180,
    libreoffice_configured: true,
    source: 'database',
  },
}

const demoIssues: ExpertReviewIssue[] = [
  {
    id: 7001, review_round_id: 5001, issue_key: 'demo-structure-1', source_issue_id: 'demo-structure-1', step_id: 'structure', severity: 'warning',
    message: '缺少施工监测专项章节', evidence: '当前方案目录未检出“施工监测”或等效章节。', anchor: { title_path: ['施工方案'], page: 2 },
    related: { suggestions: ['补充监测项目、频率、预警值和责任人。'], evidence_status: 'verified' }, disposition: 'pending', reviewer_comment: '', final_severity: null,
    reviewed_by_id: null, reviewed_at: null, created_at: demoNow, updated_at: demoNow,
  },
  {
    id: 7002, review_round_id: 5001, issue_key: 'demo-dify-1', source_issue_id: 'demo-dify-1', step_id: 'dify_workflow', severity: 'error',
    message: '连墙件布置参数前后不一致', evidence: '方案正文写“三步三跨”，计算及构造说明采用“两步三跨”。', anchor: { title_path: ['三、设计与构造'], page: 8 },
    related: { standard_no: 'JGJ 130-2011', clause: '6.4', suggestions: ['统一正文、计算书和节点图参数并复核稳定性。'], evidence_status: 'verified' }, disposition: 'pending', reviewer_comment: '', final_severity: null,
    reviewed_by_id: null, reviewed_at: null, created_at: demoNow, updated_at: demoNow,
  },
  {
    id: 7003, review_round_id: 5001, issue_key: 'demo-dify-2', source_issue_id: 'demo-dify-2', step_id: 'dify_workflow', severity: 'warning',
    message: '地基承载力依据不足', evidence: '方案仅写地面夯实和设置垫板，未提供承载力取值与沉降控制。', anchor: { title_path: ['三、设计与构造'], page: 7 },
    related: { evidence_status: 'unverified', formal_violation: false, requires_human_judgement: true, judgement: 'suspected_pending_human' }, disposition: 'pending', reviewer_comment: '', final_severity: null,
    reviewed_by_id: null, reviewed_at: null, created_at: demoNow, updated_at: demoNow,
  },
]

const expertRound: ExpertReviewRoundDetail = {
  id: 5001,
  task_id: 1001,
  document_revision_id: 3001,
  project_id: 1,
  project_name: '城市更新脚手架工程（演示）',
  project_region: '北京市海淀区',
  version_label: 'V1 缺陷演示版',
  parent_round_id: null,
  round_no: 1,
  status: 'pending',
  assigned_expert_id: null,
  assigned_expert_username: null,
  claimed_at: null,
  claim_expires_at: null,
  conclusion: null,
  final_comment: null,
  approved_at: null,
  signed_by_id: null,
  signed_at: null,
  signed_report_available: false,
  scheme_category: '脚手架工程',
  scheme_name: '落地式钢管脚手架专项施工方案',
  original_filename: '演示用_落地式脚手架专项方案_含缺陷.docx',
  task_owner_username: '项目提交人（演示）',
  review_conclusion: 'changes_required',
  completeness_status: 'complete',
  issue_count: demoIssues.length,
  pending_issue_count: demoIssues.length,
  created_at: demoNow,
  updated_at: demoNow,
  issues: demoIssues,
  decisions: [],
}

let auditEvents: AuditEventPublic[] = [
  { id: 9001, actor_id: null, entity_type: 'review_round', entity_id: '5001', action: 'created_from_ai_review', data: { task_id: 1001, issue_count: 3 }, created_at: demoNow },
]

let runtimeConfigLoaded = false
async function loadRuntimeDemoConfig() {
  if (runtimeConfigLoaded) return
  runtimeConfigLoaded = true
  try {
    const response = await fetch('/demo-config.json', { cache: 'no-store' })
    if (!response.ok) return
    const runtime = (await response.json()) as RuntimeDemoConfig
    if (runtime.scheme_types?.length) {
      schemes = runtime.scheme_types.map((item) => {
        const base = schemes.find((row) => row.id === item.id)
        const now = new Date().toISOString()
        return {
          id: item.id,
          category: item.category,
          name: item.name,
          remark: item.remark ?? base?.remark ?? '离线运行时配置',
          lifecycle_status: item.lifecycle_status ?? base?.lifecycle_status ?? 'published',
          published_at: item.published_at ?? base?.published_at ?? now,
          published_by_id: item.published_by_id ?? base?.published_by_id ?? 1,
          published_template_version_id: item.published_template_version_id ?? base?.published_template_version_id ?? item.id,
          created_at: item.created_at ?? base?.created_at ?? now,
          updated_at: item.updated_at ?? base?.updated_at ?? now,
          template_configured: item.template_configured ?? base?.template_configured ?? true,
          workflow_configured: item.workflow_configured ?? base?.workflow_configured ?? true,
          readiness_status: item.readiness_status ?? base?.readiness_status ?? 'ready',
          readiness_issues: item.readiness_issues ?? base?.readiness_issues ?? [],
        }
      })
    }
    if (runtime.projects?.length) {
      projects = runtime.projects.map((item) => {
        const base = projects.find((row) => row.id === item.id)
        return {
          id: item.id,
          name: item.name,
          region: item.region ?? base?.region ?? '',
          construction_unit: item.construction_unit ?? base?.construction_unit ?? '',
          contractor: item.contractor ?? base?.contractor ?? '',
          supervision_unit: item.supervision_unit ?? base?.supervision_unit ?? '',
          created_by_id: item.created_by_id ?? base?.created_by_id ?? 1,
          archived_at: item.archived_at ?? base?.archived_at ?? null,
          created_at: item.created_at ?? base?.created_at ?? demoNow,
          updated_at: item.updated_at ?? base?.updated_at ?? demoNow,
        }
      })
    }
    if (runtime.basis?.length) {
      basisItems = runtime.basis.map((item, index) => {
        const scheme = schemes.find((row) => row.id === Number((item as { scheme_type_id?: number }).scheme_type_id || 1)) ?? schemes[0]
        return {
          id: item.id ?? index + 1,
          basis_id: item.basis_id ?? `BASIS-RUNTIME-${index + 1}`,
          doc_type: item.doc_type ?? '', standard_no: item.standard_no ?? '', doc_name: item.doc_name ?? '',
          effect_status: item.effect_status ?? '待核验', is_mandatory: item.is_mandatory ?? false,
          scheme_category: item.scheme_category ?? scheme.category, scheme_name: item.scheme_name ?? scheme.name,
          remark: item.remark ?? null, created_at: item.created_at ?? demoNow, updated_at: item.updated_at ?? demoNow,
        }
      })
    }
    const settings = runtime.settings_example
    if (settings) {
      integrationSettings.workflow.output_variable = settings.workflow_output_variable ?? integrationSettings.workflow.output_variable
      integrationSettings.workflow.output_format = settings.workflow_output_format ?? integrationSettings.workflow.output_format
      integrationSettings.workflow.timeout_seconds = settings.workflow_timeout_seconds ?? integrationSettings.workflow.timeout_seconds
      integrationSettings.document.paddleocr_api_url = settings.paddleocr_api_url ?? integrationSettings.document.paddleocr_api_url
      onlyofficeSettings.docs_url = settings.onlyoffice_docs_url ?? onlyofficeSettings.docs_url
    }
  } catch {
    // 保留内置默认值，确保即使配置文件被误删，离线演示仍可启动。
  }
}

function ok<T>(config: InternalAxiosRequestConfig, data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: 'OK', headers: {}, config }
}

export async function demoAdapter(config: InternalAxiosRequestConfig): Promise<AxiosResponse> {
  await loadRuntimeDemoConfig()
  const method = (config.method ?? 'get').toLowerCase()
  const url = String(config.url ?? '').split('?')[0]

  if (method === 'get' && url === '/settings/review/public') {
    return ok(config, {
      system_name: reviewSettings.system_name,
      logo_url: reviewSettings.logo_url,
      favicon_url: reviewSettings.favicon_url,
      logo_configured: reviewSettings.logo_configured,
      favicon_configured: reviewSettings.favicon_configured,
    })
  }
  if (method === 'get' && url === '/settings/review') {
    return ok(config, reviewSettings)
  }
  if (method === 'put' && url === '/settings/review') {
    const form = config.data instanceof FormData ? config.data : null
    if (form) {
      reviewSettings = {
        ...reviewSettings,
        review_timeout_seconds: Number(form.get('review_timeout_seconds') || reviewSettings.review_timeout_seconds),
        prompt_debug_enabled: String(form.get('prompt_debug_enabled')) === 'true',
        worker_parallel_tasks: Number(form.get('worker_parallel_tasks') || 1),
        compilation_basis_concurrency: Number(form.get('compilation_basis_concurrency') || 1),
        context_consistency_concurrency: Number(form.get('context_consistency_concurrency') || 1),
        content_concurrency: Number(form.get('content_concurrency') || 1),
        system_name: String(form.get('system_name') || reviewSettings.system_name),
      }
    }
    return ok(config, reviewSettings)
  }
  if (method === 'get' && url === '/settings/knowledge-base') return ok(config, knowledgeBaseSettings)
  if (method === 'put' && url === '/settings/knowledge-base') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    knowledgeBaseSettings = {
      dify_base_url: String(body?.dify_base_url || knowledgeBaseSettings.dify_base_url),
      dify_dataset_name_prefix: String(body?.dify_dataset_name_prefix || ''),
      api_key_configured: Boolean(body?.dify_api_key || knowledgeBaseSettings.api_key_configured),
    }
    return ok(config, knowledgeBaseSettings)
  }
  if (method === 'post' && url === '/settings/knowledge-base/test') {
    return ok(config, {
      ok: true,
      status: 'connected',
      detail: '离线范例：知识库接口契约和测试按钮工作正常（未发出真实网络请求）。',
      latency_ms: 36,
      dataset_count: 2,
      datasets: [
        { id: 'demo-scaffold-standards', name: '危大工程-脚手架安全技术标准' },
        { id: 'demo-management-rules', name: '危大工程-安全管理规定' },
      ],
    })
  }
  if (method === 'get' && url === '/settings/knowledge-base/datasets') {
    return ok(config, [
      { id: 'demo-scaffold-standards', name: '危大工程-脚手架安全技术标准' },
      { id: 'demo-management-rules', name: '危大工程-安全管理规定' },
    ])
  }
  if (method === 'get' && url === '/settings/model-providers') return ok(config, modelProviderSettings)
  if (method === 'put' && url === '/settings/model-providers') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    modelProviderSettings = {
      ...modelProviderSettings,
      default_provider: body?.default_provider !== undefined ? body.default_provider : modelProviderSettings.default_provider,
      volcengine: { ...modelProviderSettings.volcengine, base_url: body?.volcengine_base_url ?? modelProviderSettings.volcengine.base_url, endpoint_id: body?.volcengine_endpoint_id ?? modelProviderSettings.volcengine.endpoint_id, api_key_configured: Boolean(body?.volcengine_api_key || modelProviderSettings.volcengine.api_key_configured) },
      minimax: { ...modelProviderSettings.minimax, base_url: body?.minimax_base_url ?? modelProviderSettings.minimax.base_url, model: body?.minimax_model ?? modelProviderSettings.minimax.model, api_key_configured: Boolean(body?.minimax_api_key || modelProviderSettings.minimax.api_key_configured) },
      deepseek: { ...modelProviderSettings.deepseek, base_url: body?.deepseek_base_url ?? modelProviderSettings.deepseek.base_url, model: body?.deepseek_model ?? modelProviderSettings.deepseek.model, api_key_configured: Boolean(body?.deepseek_api_key || modelProviderSettings.deepseek.api_key_configured) },
    }
    return ok(config, modelProviderSettings)
  }
  if (method === 'post' && url === '/settings/model-providers/test') {
    return ok(config, { ok: true, preview: '离线范例模型测试成功', latency_ms: 42 })
  }
  if (method === 'get' && url === '/settings/onlyoffice') return ok(config, onlyofficeSettings)
  if (method === 'put' && url === '/settings/onlyoffice') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    onlyofficeSettings = { ...onlyofficeSettings, docs_url: body?.docs_url ?? onlyofficeSettings.docs_url, callback_base_url: body?.callback_base_url ?? onlyofficeSettings.callback_base_url, editor_lang: body?.editor_lang ?? 'zh', jwt_configured: Boolean(body?.jwt_secret || onlyofficeSettings.jwt_configured) }
    return ok(config, onlyofficeSettings)
  }
  if (method === 'get' && url === '/settings/dashboard') return ok(config, dashboardSettings)
  if (method === 'put' && url === '/settings/dashboard') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    dashboardSettings = { refresh_interval_minutes: Number(body?.refresh_interval_minutes || 5) }
    return ok(config, dashboardSettings)
  }
  if (method === 'get' && url === '/settings/integrations') return ok(config, integrationSettings)
  if (method === 'put' && url === '/settings/integrations') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    integrationSettings = {
      workflow: { ...integrationSettings.workflow, enabled: Boolean(body?.dify_workflow_enabled), base_url: body?.dify_workflow_base_url ?? integrationSettings.workflow.base_url, api_key_configured: Boolean(body?.dify_workflow_api_key || integrationSettings.workflow.api_key_configured), user_prefix: body?.dify_workflow_user_prefix ?? integrationSettings.workflow.user_prefix, timeout_seconds: Number(body?.dify_workflow_timeout_seconds || 900), output_variable: body?.dify_workflow_output_variable ?? 'report', output_format: body?.dify_workflow_output_format ?? 'json', accept_partial: Boolean(body?.dify_workflow_accept_partial), continue_on_failure: Boolean(body?.dify_workflow_continue_on_failure), source: 'database' },
      document: { ...integrationSettings.document, paddleocr_api_url: body?.paddleocr_api_url ?? integrationSettings.document.paddleocr_api_url, paddleocr_api_key_configured: Boolean(body?.paddleocr_api_key || integrationSettings.document.paddleocr_api_key_configured), paddleocr_timeout_seconds: Number(body?.paddleocr_timeout_seconds || 900), convert_timeout_seconds: Number(body?.paddle_convert_timeout_seconds || 180), source: 'database' },
    }
    return ok(config, integrationSettings)
  }
  if (method === 'get' && url === '/settings/services/status') {
    return ok(config, { services: [
      { service: 'mysql', label: 'MySQL', state: 'connected', detail: '离线范例状态数据', editable: false },
      { service: 'minio', label: 'MinIO对象存储', state: 'connected', detail: '范例配置已包含', editable: false },
      { service: 'paddleocr', label: 'PaddleOCR文档解析', state: 'connected', detail: '采用PaddleOCR解析方案文档', editable: true },
      { service: 'dify_workflow', label: 'Dify Workflow', state: 'configured', detail: '输出变量 report / JSON', editable: true },
      { service: 'dify_dataset', label: 'Dify法规知识库', state: 'configured', detail: '已配置2个演示数据集', editable: true },
      { service: 'libreoffice', label: 'LibreOffice', state: 'connected', detail: 'DOCX转PDF服务', editable: false },
      { service: 'onlyoffice', label: 'OnlyOffice', state: 'configured', detail: '文档预览编辑服务', editable: true },
    ] })
  }
  if (method === 'post' && url === '/settings/integrations/test') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const service = String(body?.service || 'integration')
    return ok(config, { service, ok: true, status: 'connected', detail: `离线范例：${service} 接口配置验证成功`, latency_ms: 28, app_name: service === 'dify_workflow' ? '照片识别条件分支_v3（配置范例）' : null })
  }
  if (method === 'get' && url === '/settings/integrations/history') {
    const history: ConfigurationHistory = { items: [{ id: 1, section: 'integrations', action: 'update', actor_username: '演示管理员', changed_fields: ['dify_workflow_output_format', 'paddleocr_api_url'], created_at: demoNow, can_rollback: true }] }
    return ok(config, history)
  }
  if (method === 'post' && /^\/settings\/integrations\/history\/\d+\/rollback$/.test(url)) return ok(config, integrationSettings)
  if (method === 'get' && url === '/settings/diagnostics/download') {
    return ok(config, new Blob([JSON.stringify({ mode: 'offline-demo', services: 'configured', generated_at: new Date().toISOString() }, null, 2)], { type: 'application/json' }))
  }
  if (method === 'get' && url === '/scheme-types') return ok(config, schemes)
  if (method === 'post' && url === '/scheme-types') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const now = new Date().toISOString()
    const scheme: SchemeType = {
      id: Math.max(0, ...schemes.map((item) => item.id)) + 1,
      category: String(body?.category || '').trim(),
      name: String(body?.name || '').trim(),
      remark: String(body?.remark || '') || null,
      lifecycle_status: 'draft',
      published_at: null,
      published_by_id: null,
      published_template_version_id: null,
      created_at: now,
      updated_at: now,
      template_configured: false,
      workflow_configured: false,
      readiness_status: 'incomplete',
      readiness_issues: ['尚未上传并解析标准模板', '尚未配置审核工作流'],
    }
    schemes = [...schemes, scheme]
    return ok(config, scheme)
  }
  const schemeLifecycleMatch = url.match(/^\/scheme-types\/(\d+)\/(request-validation|publish|disable)$/)
  if (method === 'post' && schemeLifecycleMatch) {
    const id = Number(schemeLifecycleMatch[1])
    const action = schemeLifecycleMatch[2]
    const scheme = schemes.find((item) => item.id === id)
    if (scheme) {
      scheme.lifecycle_status = action === 'request-validation' ? 'pending_validation' : action === 'publish' ? 'published' : 'disabled'
      scheme.published_at = action === 'publish' ? new Date().toISOString() : null
      scheme.published_by_id = action === 'publish' ? 1 : null
      scheme.published_template_version_id = action === 'publish' ? id : null
    }
    return ok(config, scheme)
  }
  const schemeItemMatch = url.match(/^\/scheme-types\/(\d+)$/)
  if (method === 'patch' && schemeItemMatch) {
    const id = Number(schemeItemMatch[1])
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const scheme = schemes.find((item) => item.id === id)
    if (scheme) {
      Object.assign(scheme, body, {
        lifecycle_status: 'draft',
        published_at: null,
        published_by_id: null,
        published_template_version_id: null,
        updated_at: new Date().toISOString(),
      })
    }
    return ok(config, scheme)
  }
  if (method === 'delete' && schemeItemMatch) {
    const id = Number(schemeItemMatch[1])
    schemes = schemes.filter((item) => item.id !== id)
    return ok(config, null)
  }
  const readinessMatch = url.match(/^\/scheme-types\/(\d+)\/readiness$/)
  if (method === 'get' && readinessMatch) {
    const scheme = schemes.find((item) => item.id === Number(readinessMatch[1]))
    return ok(config, {
      scheme_type_id: scheme?.id,
      status: scheme?.readiness_status ?? 'unavailable',
      ready: scheme?.readiness_status === 'ready',
      issues: scheme?.readiness_issues ?? ['方案类型不存在'],
      checks: {
        template: Boolean(scheme?.template_configured),
        workflow: Boolean(scheme?.workflow_configured),
        rules: rules.some((item) => item.scheme_type_id === scheme?.id && item.enabled),
        dify_profile: true,
      },
    })
  }
  if (method === 'get' && url === '/basis') return ok(config, basisItems)
  if (method === 'post' && url === '/basis') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const now = new Date().toISOString()
    const item: BasisItem = {
      id: Math.max(0, ...basisItems.map((row) => row.id)) + 1,
      basis_id: String(body?.basis_id || `BASIS-DEMO-${Date.now()}`),
      doc_type: String(body?.doc_type || ''), standard_no: String(body?.standard_no || ''), doc_name: String(body?.doc_name || ''),
      effect_status: String(body?.effect_status || ''), is_mandatory: Boolean(body?.is_mandatory),
      scheme_category: String(body?.scheme_category || ''), scheme_name: String(body?.scheme_name || ''), remark: body?.remark ? String(body.remark) : null,
      created_at: now, updated_at: now,
    }
    basisItems = [item, ...basisItems]
    return ok(config, item)
  }
  const basisMatch = url.match(/^\/basis\/(\d+)$/)
  if (method === 'patch' && basisMatch) {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const item = basisItems.find((row) => row.id === Number(basisMatch[1]))
    if (item) Object.assign(item, body, { updated_at: new Date().toISOString() })
    return ok(config, item)
  }
  if (method === 'delete' && basisMatch) {
    basisItems = basisItems.filter((row) => row.id !== Number(basisMatch[1]))
    return ok(config, null)
  }
  const templateMatch = url.match(/^\/scheme-types\/(\d+)\/template$/)
  if (templateMatch) {
    const schemeId = Number(templateMatch[1])
    if (method === 'get') return ok(config, templates.get(schemeId) ?? null)
    if (method === 'post') {
      const form = config.data instanceof FormData ? config.data : null
      const file = form?.get('file')
      const previous = templates.get(schemeId)
      const row: TemplatePublic = {
        id: previous?.id ?? schemeId,
        scheme_type_id: schemeId,
        minio_bucket: 'smart-review-demo', object_key: `templates/demo-${schemeId}.docx`,
        original_filename: file instanceof File ? file.name : (previous?.original_filename ?? '演示模板.docx'),
        parsed_structure: previous?.parsed_structure ?? { nodes: templateNodes },
        review_workflow: previous?.review_workflow ?? { steps: ['start', 'structure', 'content', 'end'] },
        full_document_review_config: previous?.full_document_review_config ?? { review_prompt: '执行通篇审核。', dify_dataset_id: null, knowledge_keywords: [] },
        parsed_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      }
      templates.set(schemeId, row)
      const scheme = schemes.find((item) => item.id === schemeId)
      if (scheme) { scheme.template_configured = true; scheme.lifecycle_status = 'draft' }
      return ok(config, { template: row, message: previous ? 'updated' : 'created' })
    }
  }
  const templateConfigMatch = url.match(/^\/scheme-types\/(\d+)\/template\/(structure|review-workflow|full-document-review)$/)
  if (method === 'put' && templateConfigMatch) {
    const schemeId = Number(templateConfigMatch[1])
    const section = templateConfigMatch[2]
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const row = templates.get(schemeId)
    if (row) {
      if (section === 'structure') row.parsed_structure = body?.parsed_structure
      if (section === 'review-workflow') row.review_workflow = body?.review_workflow
      if (section === 'full-document-review') row.full_document_review_config = body?.full_document_review_config
      row.updated_at = new Date().toISOString()
      const scheme = schemes.find((item) => item.id === schemeId)
      if (scheme) { scheme.workflow_configured = Boolean(row.review_workflow); scheme.lifecycle_status = 'draft' }
    }
    return ok(config, row)
  }
  const profileMatch = url.match(/^\/scheme-types\/(\d+)\/dify-workflow-profile$/)
  if (profileMatch) {
    const schemeTypeId = Number(profileMatch[1])
    if (method === 'get') {
      return ok(config, schemeProfiles.get(schemeTypeId) ?? inheritedProfile(schemeTypeId))
    }
    if (method === 'put') {
      const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
      const previous = schemeProfiles.get(schemeTypeId)
      const profile: SchemeWorkflowProfilePublic = {
        scheme_type_id: schemeTypeId,
        profile_id: schemeTypeId,
        version: (previous?.version ?? 0) + 1,
        configured: true,
        source: 'scheme_profile',
        enabled: Boolean(body.enabled),
        base_url: String(body.base_url || ''),
        api_key_configured: body.clear_api_key ? false : Boolean(body.api_key || previous?.api_key_configured),
        user_prefix: String(body.user_prefix || 'smart-review'),
        timeout_seconds: Number(body.timeout_seconds || 900),
        output_variable: String(body.output_variable || 'report'),
        output_format: body.output_format || 'json',
        accept_partial: Boolean(body.accept_partial),
        continue_on_failure: Boolean(body.continue_on_failure),
        input_mapping: body.input_mapping || { documents: 'documents' },
      }
      schemeProfiles.set(schemeTypeId, profile)
      const scheme = schemes.find((item) => item.id === schemeTypeId)
      if (scheme) scheme.lifecycle_status = 'draft'
      return ok(config, profile)
    }
    if (method === 'delete') {
      schemeProfiles.delete(schemeTypeId)
      const scheme = schemes.find((item) => item.id === schemeTypeId)
      if (scheme) scheme.lifecycle_status = 'draft'
      return ok(config, inheritedProfile(schemeTypeId))
    }
  }
  if (method === 'get' && url === '/rules') {
    const schemeTypeId = Number(config.params?.scheme_type_id || 0)
    const enabledOnly = config.params?.enabled_only === true || config.params?.enabled_only === 'true'
    return ok(
      config,
      rules.filter((item) => (!schemeTypeId || item.scheme_type_id === schemeTypeId) && (!enabledOnly || item.enabled)),
    )
  }
  if (method === 'post' && url === '/rules') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const now = new Date().toISOString()
    const rule: RuleDefinition = {
      ...body,
      id: Math.max(0, ...rules.map((item) => item.id)) + 1,
      created_by_id: 1,
      created_at: now,
      updated_at: now,
    }
    rules = [rule, ...rules]
    const scheme = schemes.find((item) => item.id === rule.scheme_type_id)
    if (scheme) scheme.lifecycle_status = 'draft'
    return ok(config, rule)
  }
  const ruleMatch = url.match(/^\/rules\/(\d+)$/)
  if (method === 'patch' && ruleMatch) {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const rule = rules.find((item) => item.id === Number(ruleMatch[1]))
    if (rule) {
      Object.assign(rule, body, { updated_at: new Date().toISOString() })
      const scheme = schemes.find((item) => item.id === rule.scheme_type_id)
      if (scheme) scheme.lifecycle_status = 'draft'
    }
    return ok(config, rule)
  }
  if (method === 'get' && url === '/formulas') {
    const ruleId = Number(config.params?.rule_id || 0)
    return ok(config, formulas.filter((item) => !ruleId || item.rule_id === ruleId))
  }
  if (method === 'post' && url === '/formulas') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const now = new Date().toISOString()
    const formula: FormulaDefinition = {
      ...body,
      id: Math.max(0, ...formulas.map((item) => item.id)) + 1,
      created_at: now,
      updated_at: now,
    }
    formulas = [formula, ...formulas]
    const rule = rules.find((item) => item.id === formula.rule_id)
    const scheme = schemes.find((item) => item.id === rule?.scheme_type_id)
    if (scheme) scheme.lifecycle_status = 'draft'
    return ok(config, formula)
  }
  if (method === 'get' && url === '/users') return ok(config, users)
  if (method === 'post' && url === '/users') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const now = new Date().toISOString()
    const user: UserListItem = { id: Math.max(0, ...users.map((item) => item.id)) + 1, username: String(body?.username || ''), phone: String(body?.phone || ''), role: body?.role || 'user', created_at: now, updated_at: now }
    users = [user, ...users]
    return ok(config, user)
  }
  const userMatch = url.match(/^\/users\/(\d+)$/)
  if (method === 'patch' && userMatch) {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const user = users.find((item) => item.id === Number(userMatch[1]))
    if (user) Object.assign(user, body, { updated_at: new Date().toISOString() })
    return ok(config, user)
  }
  if (method === 'delete' && userMatch) {
    users = users.filter((item) => item.id !== Number(userMatch[1]))
    return ok(config, null)
  }
  if (method === 'get' && url === '/projects') return ok(config, projects)
  if (method === 'post' && url === '/projects') {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const now = new Date().toISOString()
    const project: ProjectPublic = {
      id: Math.max(0, ...projects.map((item) => item.id)) + 1,
      name: String(body?.name || '').trim(),
      region: String(body?.region || '').trim(),
      construction_unit: String(body?.construction_unit || '').trim(),
      contractor: String(body?.contractor || '').trim(),
      supervision_unit: String(body?.supervision_unit || '').trim(),
      created_by_id: 1,
      archived_at: null,
      created_at: now,
      updated_at: now,
    }
    projects = [project, ...projects]
    return ok(config, project)
  }
  const revisionMatch = url.match(/^\/projects\/(\d+)\/revisions$/)
  if (method === 'post' && revisionMatch) {
    const form = config.data instanceof FormData ? config.data : null
    const file = form?.get('file')
    const schemeId = Number(form?.get('scheme_type_id') ?? 1)
    const versionLabel = String(form?.get('version_label') || 'V1')
    const filename = file instanceof File ? file.name : '本地演示方案.docx'
    const task = createTask(Date.now(), filename, schemeId)
    tasks = [task, ...tasks]
    return ok(config, {
      revision: {
        id: task.id,
        project_id: Number(revisionMatch[1]),
        scheme_type_id: schemeId,
        parent_revision_id: null,
        version_label: versionLabel,
        original_filename: filename,
        sha256: 'demo-sha256',
        created_by_id: 1,
        created_at: task.created_at,
      },
      task_id: task.id,
      review_round_id: task.id,
    })
  }
  if (method === 'get' && url === '/review-tasks') return ok(config, tasks)
  if (method === 'get' && url === '/admin/dashboard/summary') {
    const today = new Date().toISOString().slice(0, 10)
    return ok(config, {
      refreshed_at: new Date().toISOString(),
      users_total: 1,
      users_admin: 1,
      users_regular: 0,
      scheme_types_total: schemes.length,
      templates_total: schemes.length,
      basis_items_total: 6,
      review_tasks_total: tasks.length,
      review_tasks_today: tasks.length,
      active_submitters_7d: 1,
      completion_rate: 1,
      tokens_total_all: 4820,
      input_tokens_total: 3560,
      output_tokens_total: 1260,
      tokens_today_total: 4820,
      input_tokens_today: 3560,
      output_tokens_today: 1260,
      tokens_window_total: 4820,
      input_tokens_window: 3560,
      output_tokens_window: 1260,
      tasks_per_day: [{ date: today, count: tasks.length }],
      tokens_per_day: [{ date: today, input_tokens: 3560, output_tokens: 1260, total_tokens: 4820 }],
      tasks_by_status: [{ status: 'succeeded', count: tasks.length }],
      tasks_by_scheme_type: [
        {
          scheme_type_id: 1,
          scheme_name: schemes[0].name,
          scheme_category: schemes[0].category,
          count: tasks.length,
        },
      ],
      dify: {
        configured: true,
        dataset_count: 2,
        segment_total: 128,
        datasets: [
          { id: 'demo-1', name: '脚手架安全技术标准', segment_count: 76, truncated: false },
          { id: 'demo-2', name: '危大工程管理规定', segment_count: 52, truncated: false },
        ],
        error: null,
        truncated: false,
      },
    })
  }
  if (method === 'post' && url === '/review-tasks') {
    const form = config.data instanceof FormData ? config.data : null
    const file = form?.get('file')
    const schemeId = Number(form?.get('scheme_type_id') ?? 1)
    const filename = file instanceof File ? file.name : '本地演示方案.docx'
    const task = createTask(Date.now(), filename, schemeId)
    tasks = [task, ...tasks]
    return ok(config, { task })
  }
  const cancelMatch = url.match(/^\/review-tasks\/(\d+)\/cancel$/)
  if (method === 'post' && cancelMatch) {
    const task = tasks.find((item) => item.id === Number(cancelMatch[1]))
    if (task) {
      task.status = 'canceled'
      task.cancel_requested_at = new Date().toISOString()
      task.finished_at = task.cancel_requested_at
      task.result_text = '任务已由用户取消，未形成审核结论。'
    }
    return ok(config, task)
  }
  const retryMatch = url.match(/^\/review-tasks\/(\d+)\/retry$/)
  if (method === 'post' && retryMatch) {
    const source = tasks.find((item) => item.id === Number(retryMatch[1])) ?? tasks[0]
    const task = createTask(Date.now(), source.original_filename, source.scheme_type_id)
    task.attempt_no = (source.attempt_no || 1) + 1
    task.retry_of_task_id = source.id
    tasks = [task, ...tasks]
    return ok(config, { task, message: `已创建重试任务 #${task.id}` })
  }
  if (method === 'delete' && /^\/review-tasks\/\d+$/.test(url)) {
    const id = Number(url.split('/').pop())
    tasks = tasks.filter((item) => item.id !== id)
    return ok(config, null)
  }
  const detailMatch = url.match(/^\/review-tasks\/(\d+)$/)
  if (method === 'get' && detailMatch) {
    const task = tasks.find((item) => item.id === Number(detailMatch[1])) ?? tasks[0]
    return ok(config, task)
  }
  if (method === 'get' && url === '/expert/review-rounds') {
    const status = String(config.params?.status || '')
    const rows = !status || expertRound.status === status ? [expertRound] : []
    return ok(config, rows)
  }
  if (method === 'post' && url === '/expert/review-rounds/sync') return ok(config, { created: 0 })
  const expertDetailMatch = url.match(/^\/expert\/review-rounds\/(\d+)$/)
  if (method === 'get' && expertDetailMatch) return ok(config, expertRound)
  const expertClaimMatch = url.match(/^\/expert\/review-rounds\/(\d+)\/claim$/)
  if (method === 'post' && expertClaimMatch) {
    expertRound.status = 'in_review'
    expertRound.assigned_expert_id = 1
    expertRound.assigned_expert_username = '演示管理员'
    expertRound.claimed_at = new Date().toISOString()
    expertRound.claim_expires_at = new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString()
    expertRound.updated_at = expertRound.claimed_at
    auditEvents = [{ id: Date.now(), actor_id: 1, entity_type: 'review_round', entity_id: String(expertRound.id), action: 'claimed', data: {}, created_at: expertRound.claimed_at }, ...auditEvents]
    return ok(config, expertRound)
  }
  const expertReleaseMatch = url.match(/^\/expert\/review-rounds\/(\d+)\/release$/)
  if (method === 'post' && expertReleaseMatch) {
    expertRound.status = 'pending'
    expertRound.assigned_expert_id = null
    expertRound.assigned_expert_username = null
    expertRound.claimed_at = null
    expertRound.claim_expires_at = null
    expertRound.updated_at = new Date().toISOString()
    return ok(config, expertRound)
  }
  const expertIssueMatch = url.match(/^\/expert\/review-rounds\/(\d+)\/issues\/(\d+)$/)
  if (method === 'patch' && expertIssueMatch) {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const issue = expertRound.issues.find((item) => item.id === Number(expertIssueMatch[2]))
    if (issue) {
      Object.assign(issue, body, { reviewed_by_id: 1, reviewed_at: new Date().toISOString(), updated_at: new Date().toISOString() })
      expertRound.pending_issue_count = expertRound.issues.filter((item) => item.disposition === 'pending').length
    }
    return ok(config, issue)
  }
  const expertActionMatch = url.match(/^\/expert\/review-rounds\/(\d+)\/(approve|request-changes|sign)$/)
  if (method === 'post' && expertActionMatch) {
    const action = expertActionMatch[2]
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const now = new Date().toISOString()
    if (action === 'approve') {
      expertRound.status = 'approved'; expertRound.conclusion = body?.conclusion || 'passed'; expertRound.final_comment = body?.comment || ''; expertRound.approved_at = now
    } else if (action === 'request-changes') {
      expertRound.status = 'changes_requested'; expertRound.conclusion = body?.conclusion || 'changes_required'; expertRound.final_comment = body?.comment || ''
    } else {
      expertRound.status = 'signed'; expertRound.signed_by_id = 1; expertRound.signed_at = now; expertRound.signed_report_available = true
    }
    expertRound.updated_at = now
    auditEvents = [{ id: Date.now(), actor_id: 1, entity_type: 'review_round', entity_id: String(expertRound.id), action, data: { conclusion: expertRound.conclusion }, created_at: now }, ...auditEvents]
    return ok(config, expertRound)
  }
  if (method === 'get' && url === '/expert/audit-events') return ok(config, auditEvents)
  if (method === 'get' && /^\/expert\/review-rounds\/\d+\/source-download$/.test(url)) {
    return ok(config, { url: '/demo-assets/%E6%BC%94%E7%A4%BA%E7%94%A8_%E8%90%BD%E5%9C%B0%E5%BC%8F%E8%84%9A%E6%89%8B%E6%9E%B6%E4%B8%93%E9%A1%B9%E6%96%B9%E6%A1%88_%E5%90%AB%E7%BC%BA%E9%99%B7.docx', filename: '演示用_落地式脚手架专项方案_含缺陷.docx', sha256: 'demo-source-sha256', expires_seconds: 3600 })
  }
  if (method === 'get' && /^\/expert\/review-rounds\/\d+\/signed-report$/.test(url)) {
    return ok(config, { url: '/demo-assets/%E8%84%9A%E6%89%8B%E6%9E%B6%E4%B8%93%E9%A1%B9%E6%96%B9%E6%A1%88_%E6%BC%94%E7%A4%BA%E5%AE%A1%E6%9F%A5%E6%8A%A5%E5%91%8A.docx', sha256: 'demo-signed-report-sha256', expires_seconds: 3600 })
  }
  if (method === 'get' && /\/output-download-url$/.test(url)) {
    return ok(config, {
      url: '/demo-assets/%E8%84%9A%E6%89%8B%E6%9E%B6%E4%B8%93%E9%A1%B9%E6%96%B9%E6%A1%88_%E6%BC%94%E7%A4%BA%E5%AE%A1%E6%9F%A5%E6%8A%A5%E5%91%8A.docx',
    })
  }
  if (method === 'get' && /\/audit-report$/.test(url)) {
    const response = await fetch(
      '/demo-assets/%E8%84%9A%E6%89%8B%E6%9E%B6%E4%B8%93%E9%A1%B9%E6%96%B9%E6%A1%88_%E6%BC%94%E7%A4%BA%E5%AE%A1%E6%9F%A5%E6%8A%A5%E5%91%8A.docx',
    )
    return ok(config, await response.blob())
  }
  if (method === 'get' && /\/template\/download-url$/.test(url)) {
    return ok(config, { url: '/demo-assets/%E8%90%BD%E5%9C%B0%E5%BC%8F%E8%84%9A%E6%89%8B%E6%9E%B6%E4%B8%93%E9%A1%B9%E6%96%B9%E6%A1%88_%E6%A0%87%E5%87%86%E6%A8%A1%E6%9D%BF.docx' })
  }

  return ok(config, [])
}
