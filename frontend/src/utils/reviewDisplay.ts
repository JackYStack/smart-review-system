export const REVIEW_STEP_LABELS: Record<string, string> = {
  structure: '结构审核',
  compilation_basis: '编制依据审核',
  context_consistency: '上下文一致性',
  content: '内容审核',
  full_document: '通篇审核',
  dify_workflow: 'Dify Workflow 全文审查',
  rules_and_formulas: '规则与公式验算',
}

const RELATED_FIELD_LABELS: Record<string, string> = {
  evidence_status: '证据状态',
  formal_violation: '正式违规判定',
  requires_human_judgement: '人工专业判断',
  judgement: '判断状态',
  rule_code: '规则编号',
  rule_version: '规则版本',
  rule_type: '规则类型',
  standard_no: '标准编号',
  standard_name: '标准名称',
  standard_version: '标准版本',
  clause_no: '条款号',
  clause_text: '条款内容',
  calculation_result_id: '验算记录编号',
  technical_error: '技术异常',
  component: '技术组件',
  completeness_impact: '对审查完整性的影响',
  integration_error: '外部服务异常',
  integration_warning: '外部服务警告',
  report_format: '报告格式',
  risk_level: '风险等级',
  standards: '审查依据',
  required_materials: '复核所需资料',
  regulation: '法规依据',
  gap: '问题差距',
  inputs: '输入参数',
  steps: '计算步骤',
  expected: '判定条件',
  expression: '计算公式',
  comparator: '比较符',
  threshold: '阈值',
  parameter: '参数名称',
  value: '数值',
  unit: '单位',
  raw_value: '原始值',
  source: '数据来源',
  extraction_method: '提取方式',
  confidence: '置信度',
  verified: '是否已核验',
  verified_by_id: '核验人员编号',
  page_no: '页码',
  quote: '原文摘录',
  section: '章节',
  note: '说明',
}

const VALUE_LABELS: Record<string, string> = {
  verified: '已核验',
  unverified: '尚未核验',
  technical: '技术异常',
  suspected_pending_human: '疑似问题，待人工复核',
  required_section: '必备章节检查',
  parameter_range: '参数范围检查',
  cross_field: '跨字段一致性检查',
  formula: '公式验算',
  complete: '完整',
  partial: '部分完成',
  degraded: '降级结果',
  unavailable: '不可用',
  manual: '人工录入',
  regex: '正则提取',
  llm: '大模型提取',
  table: '表格提取',
  json: 'JSON结构化数据',
  markdown: 'Markdown文本',
  text: '普通文本',
}

const PRIMARY_RELATED_KEYS = new Set([
  'evidence_status',
  'formal_violation',
  'requires_human_judgement',
  'judgement',
  'rule_code',
  'rule_version',
  'rule_type',
  'standard_no',
  'standard_name',
  'standard_version',
  'clause_no',
  'clause_text',
  'calculation_result_id',
  'technical_error',
  'component',
  'completeness_impact',
  'integration_error',
  'integration_warning',
  'report_format',
  'risk_level',
  'standards',
  'required_materials',
  'regulation',
  'gap',
])

function booleanLabel(key: string, value: boolean): string {
  if (key === 'formal_violation') return value ? '已具备正式违规判定条件' : '尚不能认定为正式违规'
  if (key === 'requires_human_judgement') return value ? '需要专业人员判断' : '无需额外人工判断'
  if (key === 'verified') return value ? '已核验' : '尚未核验'
  if (key === 'technical_error') return value ? '存在' : '不存在'
  if (key === 'integration_error') return value ? '存在' : '不存在'
  if (key === 'integration_warning') return value ? '存在' : '不存在'
  return value ? '是' : '否'
}

function translateValue(key: string, value: unknown): unknown {
  if (typeof value === 'boolean') return booleanLabel(key, value)
  if (typeof value === 'string') return VALUE_LABELS[value.trim().toLowerCase()] ?? value
  if (Array.isArray(value)) return value.map((item) => translateValue('', item))
  if (value && typeof value === 'object') return translateReviewMetadata(value as Record<string, unknown>)
  return value
}

export function translateReviewMetadata(
  metadata: Record<string, unknown> | undefined,
): Record<string, unknown> {
  if (!metadata) return {}
  return Object.fromEntries(
    Object.entries(metadata).map(([key, value]) => [
      RELATED_FIELD_LABELS[key] ?? key,
      translateValue(key, value),
    ]),
  )
}

function displayValue(key: string, value: unknown): string {
  const translated = translateValue(key, value)
  if (Array.isArray(translated)) {
    return translated
      .map((item) => (typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item)))
      .join('、')
  }
  if (translated && typeof translated === 'object') return JSON.stringify(translated, null, 2)
  return String(translated ?? '').trim()
}

export function relatedMetadataText(metadata: Record<string, unknown> | undefined): string {
  if (!metadata) return ''
  return Object.entries(metadata)
    .filter(([key, value]) => {
      if (!PRIMARY_RELATED_KEYS.has(key)) return false
      if (value === undefined || value === null) return false
      return String(value).trim().length > 0
    })
    .map(([key, value]) => `${RELATED_FIELD_LABELS[key]}：${displayValue(key, value)}`)
    .join('；')
}
