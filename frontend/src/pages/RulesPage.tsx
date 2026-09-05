import {
  CalculatorOutlined,
  EditOutlined,
  FileExcelOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type {
  FormulaDefinition,
  RuleDefinition,
  RuleSeverity,
  RuleType,
  SchemeType,
} from '../api/types'
import PageShell from '../components/PageShell'
import { DEFAULT_TABLE_PAGINATION } from '../config/tablePagination'
import { formatApiErrorMessage } from '../utils/apiError'

const { Paragraph, Text, Title } = Typography

const RULE_TYPE_VIEW: Record<RuleType, { label: string; color: string }> = {
  required_section: { label: '必备章节', color: 'blue' },
  parameter_range: { label: '参数范围', color: 'purple' },
  cross_field: { label: '跨章节一致性', color: 'cyan' },
  formula: { label: '公式验算', color: 'gold' },
}

const SEVERITY_VIEW: Record<RuleSeverity, { label: string; color: string }> = {
  error: { label: '严重', color: 'error' },
  warning: { label: '警告', color: 'warning' },
  info: { label: '提示', color: 'processing' },
}

const RULE_CONFIG_EXAMPLES: Record<RuleType, Record<string, unknown>> = {
  required_section: { keywords: ['施工监测', '监测预警'], match: 'all' },
  parameter_range: { parameter: 'scaffold_height', min: 0, max: 24, unit: 'm' },
  cross_field: {
    left: 'design_spacing',
    right: 'drawing_spacing',
    operator: '==',
    tolerance: 0,
  },
  formula: {},
}

const RULE_TYPE_OPTIONS = Object.entries(RULE_TYPE_VIEW).map(([value, view]) => ({
  value,
  label: view.label,
}))

const SEVERITY_OPTIONS = Object.entries(SEVERITY_VIEW).map(([value, view]) => ({
  value,
  label: view.label,
}))

type RuleFormValues = {
  scheme_type_id: number
  rule_code: string
  version: number
  name: string
  rule_type: RuleType
  severity: RuleSeverity
  enabled: boolean
  config_json: string
  source_standard_no: string
  source_standard_name: string
  source_version: string
  source_clause: string
  source_text: string
}

type FormulaFormValues = {
  rule_id: number
  formula_code: string
  version: number
  name: string
  expression: string
  variables_json: string
  result_unit: string
  comparator: FormulaDefinition['comparator']
  threshold_mode: 'value' | 'parameter'
  threshold_value?: string
  threshold_parameter?: string
  enabled: boolean
}

function parseJsonObject(raw: string, label: string): Record<string, unknown> {
  let value: unknown
  try {
    value = JSON.parse(raw || '{}')
  } catch {
    throw new Error(`${label}不是有效的 JSON`)
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label}必须是 JSON 对象`)
  }
  return value as Record<string, unknown>
}

function validateRuleConfig(ruleType: RuleType, config: Record<string, unknown>): void {
  if (ruleType === 'required_section') {
    const keywords = config.keywords
    if (!Array.isArray(keywords) || !keywords.some((item) => String(item ?? '').trim())) {
      throw new Error('必备章节规则必须配置非空 keywords 数组')
    }
    if (config.match != null && !['all', 'any'].includes(String(config.match))) {
      throw new Error('match 只能是 all 或 any')
    }
    return
  }
  if (ruleType === 'parameter_range') {
    if (!String(config.parameter ?? '').trim()) {
      throw new Error('参数范围规则必须配置 parameter')
    }
    if (config.min == null && config.max == null) {
      throw new Error('参数范围规则至少配置 min 或 max')
    }
    const minimum = config.min == null ? null : Number(config.min)
    const maximum = config.max == null ? null : Number(config.max)
    if ((minimum != null && !Number.isFinite(minimum)) || (maximum != null && !Number.isFinite(maximum))) {
      throw new Error('min 和 max 必须是数值')
    }
    if (minimum != null && maximum != null && minimum > maximum) {
      throw new Error('min 不能大于 max')
    }
    return
  }
  if (ruleType === 'cross_field') {
    const left = String(config.left ?? '').trim()
    const right = String(config.right ?? '').trim()
    if (!left || !right || left === right) {
      throw new Error('跨章节规则必须配置两个不同的参数 left 和 right')
    }
    if (config.operator != null && !['<', '<=', '==', '>=', '>', '!='].includes(String(config.operator))) {
      throw new Error('operator 仅支持 <、<=、==、>=、>、!=')
    }
    const tolerance = Number(config.tolerance ?? 0)
    if (!Number.isFinite(tolerance) || tolerance < 0) {
      throw new Error('tolerance 必须是非负数值')
    }
  }
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

export default function RulesPage() {
  const qc = useQueryClient()
  const { message } = AntApp.useApp()
  const [selectedSchemeId, setSelectedSchemeId] = useState<number>()
  const [ruleModalOpen, setRuleModalOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<RuleDefinition | null>(null)
  const [formulaModalOpen, setFormulaModalOpen] = useState(false)
  const [formulaRuleFilter, setFormulaRuleFilter] = useState<number>()
  const [ruleForm] = Form.useForm<RuleFormValues>()
  const [formulaForm] = Form.useForm<FormulaFormValues>()
  const ruleType = Form.useWatch('rule_type', ruleForm)
  const thresholdMode = Form.useWatch('threshold_mode', formulaForm)

  const { data: schemes = [], isLoading: schemesLoading } = useQuery({
    queryKey: ['schemes'],
    queryFn: async () => {
      const { data } = await api.get<SchemeType[]>('/scheme-types', {
        params: { include_unpublished: true },
      })
      return data
    },
  })

  const effectiveSchemeId = selectedSchemeId ?? schemes[0]?.id

  const {
    data: rules = [],
    isLoading: rulesLoading,
    isError: rulesError,
    error: rulesQueryError,
    refetch: refetchRules,
  } = useQuery({
    queryKey: ['rules', effectiveSchemeId],
    enabled: effectiveSchemeId != null,
    queryFn: async () => {
      const { data } = await api.get<RuleDefinition[]>('/rules', {
        params: { scheme_type_id: effectiveSchemeId },
      })
      return data
    },
  })

  const {
    data: allFormulas = [],
    isLoading: formulasLoading,
    isError: formulasError,
    error: formulasQueryError,
    refetch: refetchFormulas,
  } = useQuery({
    queryKey: ['formulas', effectiveSchemeId],
    enabled: effectiveSchemeId != null,
    queryFn: async () => {
      const { data } = await api.get<FormulaDefinition[]>('/formulas')
      return data
    },
  })

  const schemeOptions = useMemo(
    () => schemes.map((item) => ({ value: item.id, label: `${item.category} / ${item.name}` })),
    [schemes],
  )
  const ruleById = useMemo(() => new Map(rules.map((item) => [item.id, item])), [rules])
  const formulaRules = useMemo(() => rules.filter((item) => item.rule_type === 'formula'), [rules])
  const formulaRuleOptions = useMemo(
    () => formulaRules.map((item) => ({ value: item.id, label: `${item.rule_code} v${item.version} · ${item.name}` })),
    [formulaRules],
  )
  const formulas = useMemo(() => {
    const availableRuleIds = new Set(rules.map((item) => item.id))
    return allFormulas.filter(
      (item) => availableRuleIds.has(item.rule_id) && (formulaRuleFilter == null || item.rule_id === formulaRuleFilter),
    )
  }, [allFormulas, formulaRuleFilter, rules])

  const saveRuleMutation = useMutation({
    mutationFn: async (values: RuleFormValues) => {
      const config = parseJsonObject(values.config_json, '规则配置')
      validateRuleConfig(values.rule_type, config)
      if (editingRule) {
        const body = {
          name: values.name,
          severity: values.severity,
          enabled: values.enabled,
          config,
          source_standard_no: values.source_standard_no,
          source_standard_name: values.source_standard_name,
          source_version: values.source_version,
          source_clause: values.source_clause,
          source_text: values.source_text,
        }
        const { data } = await api.patch<RuleDefinition>(`/rules/${editingRule.id}`, body)
        return data
      }
      const body = {
        scheme_type_id: values.scheme_type_id,
        rule_code: values.rule_code,
        version: values.version,
        name: values.name,
        rule_type: values.rule_type,
        severity: values.severity,
        enabled: values.enabled,
        config,
        source_standard_no: values.source_standard_no,
        source_standard_name: values.source_standard_name,
        source_version: values.source_version,
        source_clause: values.source_clause,
        source_text: values.source_text,
      }
      const { data } = await api.post<RuleDefinition>('/rules', body)
      return data
    },
    onSuccess: async () => {
      message.success(editingRule ? '规则已更新；方案类型需重新验证后发布' : '规则已创建')
      setRuleModalOpen(false)
      setEditingRule(null)
      ruleForm.resetFields()
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['rules', effectiveSchemeId] }),
        qc.invalidateQueries({ queryKey: ['schemes'] }),
      ])
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '保存规则失败')),
  })

  const createFormulaMutation = useMutation({
    mutationFn: async (values: FormulaFormValues) => {
      const variables = parseJsonObject(values.variables_json, '变量映射')
      const body = {
        rule_id: values.rule_id,
        formula_code: values.formula_code,
        version: values.version,
        name: values.name,
        expression: values.expression,
        variables,
        result_unit: values.result_unit,
        comparator: values.comparator,
        threshold_value: values.threshold_mode === 'value' ? values.threshold_value : null,
        threshold_parameter: values.threshold_mode === 'parameter' ? values.threshold_parameter : null,
        enabled: values.enabled,
      }
      const { data } = await api.post<FormulaDefinition>('/formulas', body)
      return data
    },
    onSuccess: async () => {
      message.success('公式已创建；方案类型需重新验证后发布')
      setFormulaModalOpen(false)
      formulaForm.resetFields()
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['formulas', effectiveSchemeId] }),
        qc.invalidateQueries({ queryKey: ['schemes'] }),
      ])
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '创建公式失败')),
  })

  function openCreateRule() {
    if (effectiveSchemeId == null) return
    setEditingRule(null)
    ruleForm.setFieldsValue({
      scheme_type_id: effectiveSchemeId,
      rule_code: '',
      version: 1,
      name: '',
      rule_type: 'required_section',
      severity: 'error',
      enabled: true,
      config_json: formatJson(RULE_CONFIG_EXAMPLES.required_section),
      source_standard_no: '',
      source_standard_name: '',
      source_version: '',
      source_clause: '',
      source_text: '',
    })
    setRuleModalOpen(true)
  }

  function openEditRule(row: RuleDefinition) {
    setEditingRule(row)
    ruleForm.setFieldsValue({
      scheme_type_id: row.scheme_type_id,
      rule_code: row.rule_code,
      version: row.version,
      name: row.name,
      rule_type: row.rule_type,
      severity: row.severity,
      enabled: row.enabled,
      config_json: formatJson(row.config),
      source_standard_no: row.source_standard_no,
      source_standard_name: row.source_standard_name,
      source_version: row.source_version,
      source_clause: row.source_clause,
      source_text: row.source_text,
    })
    setRuleModalOpen(true)
  }

  function openCreateFormula() {
    const defaultRuleId = formulaRuleFilter ?? formulaRules[0]?.id
    if (defaultRuleId == null) {
      message.warning('请先新建一条“公式验算”类型的规则')
      return
    }
    formulaForm.setFieldsValue({
      rule_id: defaultRuleId,
      formula_code: '',
      version: 1,
      name: '',
      expression: '',
      variables_json: formatJson({ load: { parameter: 'design_load', unit: 'kN' } }),
      result_unit: 'kN',
      comparator: '<=',
      threshold_mode: 'value',
      threshold_value: '',
      threshold_parameter: '',
      enabled: true,
    })
    setFormulaModalOpen(true)
  }

  const ruleColumns = [
    {
      title: '规则',
      key: 'rule',
      width: 250,
      render: (_: unknown, row: RuleDefinition) => (
        <Space direction="vertical" size={0}>
          <Text strong>{row.name}</Text>
          <Text type="secondary" code>{row.rule_code} · v{row.version}</Text>
        </Space>
      ),
    },
    {
      title: '类型 / 等级',
      key: 'type',
      width: 180,
      render: (_: unknown, row: RuleDefinition) => (
        <Space wrap size={[4, 4]}>
          <Tag color={RULE_TYPE_VIEW[row.rule_type].color}>{RULE_TYPE_VIEW[row.rule_type].label}</Tag>
          <Tag color={SEVERITY_VIEW[row.severity].color}>{SEVERITY_VIEW[row.severity].label}</Tag>
        </Space>
      ),
    },
    {
      title: '法规证据',
      key: 'source',
      width: 310,
      render: (_: unknown, row: RuleDefinition) => (
        <Space direction="vertical" size={0}>
          <Text>{[row.source_standard_no, row.source_clause].filter(Boolean).join(' · ') || '未配置'}</Text>
          <Tooltip title={row.source_standard_name}>
            <Text type="secondary" ellipsis style={{ maxWidth: 290 }}>{row.source_standard_name || '缺少规范名称'}</Text>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      width: 86,
      render: (enabled: boolean) => enabled ? <Tag color="success">启用</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 170,
      render: (value: string) => formatTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right' as const,
      width: 100,
      render: (_: unknown, row: RuleDefinition) => (
        <Button type="link" icon={<EditOutlined />} onClick={() => openEditRule(row)}>编辑</Button>
      ),
    },
  ]

  const formulaColumns = [
    {
      title: '公式',
      key: 'formula',
      width: 250,
      render: (_: unknown, row: FormulaDefinition) => (
        <Space direction="vertical" size={0}>
          <Text strong>{row.name}</Text>
          <Text type="secondary" code>{row.formula_code} · v{row.version}</Text>
        </Space>
      ),
    },
    {
      title: '所属规则',
      dataIndex: 'rule_id',
      width: 240,
      render: (ruleId: number) => {
        const rule = ruleById.get(ruleId)
        return rule ? `${rule.rule_code} v${rule.version} · ${rule.name}` : `#${ruleId}`
      },
    },
    {
      title: '确定性表达式',
      dataIndex: 'expression',
      width: 260,
      render: (value: string) => <Text code copyable>{value}</Text>,
    },
    {
      title: '判定阈值',
      key: 'threshold',
      width: 210,
      render: (_: unknown, row: FormulaDefinition) => (
        <Text>
          结果 {row.comparator}{' '}
          {row.threshold_parameter ? `参数 ${row.threshold_parameter}` : `${row.threshold_value ?? '—'} ${row.result_unit}`}
        </Text>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      width: 86,
      render: (enabled: boolean) => enabled ? <Tag color="success">启用</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (value: string) => formatTime(value),
    },
  ]

  const tabs = [
    {
      key: 'rules',
      label: `规则（${rules.length}）`,
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            showIcon
            type="info"
            message="确定性规则用于最终判定"
            description="规则必须绑定可追溯的规范编号、条款号和条款原文。修改规则会使已发布方案类型回到待验证状态，但不会改变历史任务保存的配置快照。"
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button type="primary" icon={<PlusOutlined />} disabled={effectiveSchemeId == null} onClick={openCreateRule}>
              新建规则
            </Button>
          </div>
          {rulesError ? (
            <Alert
              type="error"
              showIcon
              message="规则加载失败"
              description={formatApiErrorMessage(rulesQueryError, '无法读取规则列表')}
              action={<Button onClick={() => void refetchRules()}>重试</Button>}
            />
          ) : null}
          <Table<RuleDefinition>
            rowKey="id"
            loading={rulesLoading}
            dataSource={rules}
            columns={ruleColumns}
            scroll={{ x: 1300 }}
            locale={{ emptyText: effectiveSchemeId == null ? '请先创建方案类型' : '当前方案类型还没有规则' }}
            pagination={DEFAULT_TABLE_PAGINATION}
          />
        </Space>
      ),
    },
    {
      key: 'formulas',
      label: `公式（${formulas.length}）`,
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            showIcon
            type="warning"
            message="大模型只负责抽取参数，数值结论由公式引擎计算"
            description="表达式仅允许安全数学运算以及 abs、min、max、sqrt；变量必须在 JSON 映射中逐一声明。每个公式必须且只能选择固定阈值或参数阈值之一。"
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <Select
              allowClear
              placeholder="按所属公式规则筛选"
              value={formulaRuleFilter}
              options={formulaRuleOptions}
              style={{ width: 380, maxWidth: '100%' }}
              onChange={setFormulaRuleFilter}
            />
            <Button type="primary" icon={<PlusOutlined />} disabled={formulaRules.length === 0} onClick={openCreateFormula}>
              新建公式
            </Button>
          </div>
          {formulaRules.length === 0 && !rulesLoading ? (
            <Alert type="info" showIcon message="请先在“规则”页签新建一条“公式验算”类型规则，再添加公式定义。" />
          ) : null}
          {formulasError ? (
            <Alert
              type="error"
              showIcon
              message="公式加载失败"
              description={formatApiErrorMessage(formulasQueryError, '无法读取公式列表')}
              action={<Button onClick={() => void refetchFormulas()}>重试</Button>}
            />
          ) : null}
          <Table<FormulaDefinition>
            rowKey="id"
            loading={formulasLoading || rulesLoading}
            dataSource={formulas}
            columns={formulaColumns}
            scroll={{ x: 1250 }}
            locale={{ emptyText: '当前筛选范围没有公式' }}
            pagination={DEFAULT_TABLE_PAGINATION}
          />
        </Space>
      ),
    },
    {
      key: 'excel',
      label: 'Excel 批量导入',
      children: <ExcelEtlGuide schemeTypeId={effectiveSchemeId} />,
    },
  ]

  return (
    <PageShell
      icon={<CalculatorOutlined />}
      description="配置可复现的必备章节、参数阈值、跨章节一致性规则与安全公式；所有正式违规结论都应具有法规证据。"
      extra={
        <Select
          showSearch
          optionFilterProp="label"
          loading={schemesLoading}
          value={effectiveSchemeId}
          placeholder="选择方案类型"
          options={schemeOptions}
          style={{ minWidth: 360, maxWidth: '100%' }}
          onChange={(value) => {
            setSelectedSchemeId(value)
            setFormulaRuleFilter(undefined)
          }}
        />
      }
    >
      {schemes.length === 0 && !schemesLoading ? (
        <Alert type="warning" showIcon message="尚无方案类型，请先到“方案类型管理”创建草稿。" />
      ) : (
        <Tabs items={tabs} destroyOnHidden={false} />
      )}

      <Modal
        title={editingRule ? '编辑确定性规则' : '新建确定性规则'}
        open={ruleModalOpen}
        width={900}
        okText="保存规则"
        confirmLoading={saveRuleMutation.isPending}
        onOk={() => void ruleForm.submit()}
        onCancel={() => {
          setRuleModalOpen(false)
          setEditingRule(null)
          ruleForm.resetFields()
        }}
        destroyOnClose
      >
        <Form<RuleFormValues>
          form={ruleForm}
          layout="vertical"
          requiredMark="optional"
          onFinish={(values) => saveRuleMutation.mutate(values)}
        >
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item name="scheme_type_id" label="方案类型" rules={[{ required: true }]}>
                <Select disabled options={schemeOptions} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="rule_code" label="规则编号" rules={[{ required: true, whitespace: true }]}>
                <Input disabled={editingRule != null} placeholder="如 SCAFFOLD-STRUCT-001" maxLength={128} />
              </Form.Item>
            </Col>
            <Col xs={24} md={4}>
              <Form.Item name="version" label="版本" rules={[{ required: true }]}>
                <InputNumber disabled={editingRule != null} min={1} precision={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item name="name" label="规则名称" rules={[{ required: true, whitespace: true }]}>
                <Input maxLength={255} />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item name="rule_type" label="规则类型" rules={[{ required: true }]}>
                <Select
                  disabled={editingRule != null}
                  options={RULE_TYPE_OPTIONS}
                  onChange={(value: RuleType) => ruleForm.setFieldValue('config_json', formatJson(RULE_CONFIG_EXAMPLES[value]))}
                />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="severity" label="严重等级" rules={[{ required: true }]}>
                <Select options={SEVERITY_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={12} md={2}>
              <Form.Item name="enabled" label="启用" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="config_json"
            label="规则配置（JSON）"
            extra={ruleType ? `当前类型：${RULE_TYPE_VIEW[ruleType].label}。字段示例已自动填入，可直接修改。` : undefined}
            rules={[
              { required: true, whitespace: true, message: '请输入 JSON 配置' },
              {
                validator: async (_, value: string) => {
                  const config = parseJsonObject(value, '规则配置')
                  validateRuleConfig(ruleForm.getFieldValue('rule_type'), config)
                },
              },
            ]}
          >
            <Input.TextArea autoSize={{ minRows: 5, maxRows: 12 }} spellCheck={false} style={{ fontFamily: 'Consolas, monospace' }} />
          </Form.Item>

          <Divider titlePlacement="start"><SafetyCertificateOutlined /> 法规证据</Divider>
          <Alert
            type="info"
            showIcon
            message="规范编号、条款号与条款原文用于生成可追溯证据链；缺失这些字段的结论只能降级为待人工判断。"
            style={{ marginBottom: 16 }}
          />
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item name="source_standard_no" label="规范编号" rules={[{ required: true, whitespace: true }]}>
                <Input placeholder="如 JGJ 130-2011" maxLength={128} />
              </Form.Item>
            </Col>
            <Col xs={24} md={10}>
              <Form.Item name="source_standard_name" label="规范名称" rules={[{ required: true, whitespace: true }]}>
                <Input maxLength={512} />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item name="source_version" label="版本 / 年份">
                <Input maxLength={64} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="source_clause" label="条款号" rules={[{ required: true, whitespace: true }]}>
            <Input placeholder="如 6.4.2" maxLength={128} />
          </Form.Item>
          <Form.Item name="source_text" label="条款原文" rules={[{ required: true, whitespace: true }]}>
            <Input.TextArea autoSize={{ minRows: 4, maxRows: 10 }} maxLength={12000} showCount />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="新建确定性公式"
        open={formulaModalOpen}
        width={820}
        okText="创建公式"
        confirmLoading={createFormulaMutation.isPending}
        onOk={() => void formulaForm.submit()}
        onCancel={() => {
          setFormulaModalOpen(false)
          formulaForm.resetFields()
        }}
        destroyOnClose
      >
        <Form<FormulaFormValues>
          form={formulaForm}
          layout="vertical"
          requiredMark="optional"
          onFinish={(values) => createFormulaMutation.mutate(values)}
        >
          <Form.Item name="rule_id" label="所属公式规则" rules={[{ required: true }]}>
            <Select options={formulaRuleOptions} showSearch optionFilterProp="label" />
          </Form.Item>
          <Row gutter={16}>
            <Col xs={24} md={10}>
              <Form.Item name="formula_code" label="公式编号" rules={[{ required: true, whitespace: true }]}>
                <Input placeholder="如 SCAFFOLD-LOAD-001" maxLength={128} />
              </Form.Item>
            </Col>
            <Col xs={24} md={4}>
              <Form.Item name="version" label="版本" rules={[{ required: true }]}>
                <InputNumber min={1} precision={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={10}>
              <Form.Item name="name" label="公式名称" rules={[{ required: true, whitespace: true }]}>
                <Input maxLength={255} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="expression"
            label="表达式"
            extra="示例：(load * factor) / capacity；变量名必须在下方 JSON 中声明。"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input.TextArea rows={3} spellCheck={false} style={{ fontFamily: 'Consolas, monospace' }} maxLength={4000} />
          </Form.Item>
          <Form.Item
            name="variables_json"
            label="变量映射（JSON）"
            rules={[
              { required: true, whitespace: true },
              {
                validator: async (_, value: string) => {
                  const variables = parseJsonObject(value, '变量映射')
                  const invalid = Object.keys(variables).find((name) => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(name))
                  if (invalid) throw new Error(`变量名无效：${invalid}`)
                },
              },
            ]}
          >
            <Input.TextArea autoSize={{ minRows: 5, maxRows: 12 }} spellCheck={false} style={{ fontFamily: 'Consolas, monospace' }} />
          </Form.Item>
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item name="result_unit" label="结果单位">
                <Input placeholder="如 kN、MPa、mm" maxLength={32} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="comparator" label="比较符" rules={[{ required: true }]}>
                <Select options={['<', '<=', '==', '>=', '>', '!='].map((value) => ({ value, label: value }))} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="enabled" label="启用" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="threshold_mode" label="阈值来源" rules={[{ required: true }]}>
            <Radio.Group
              options={[
                { label: '固定阈值', value: 'value' },
                { label: '任务参数阈值', value: 'parameter' },
              ]}
              optionType="button"
            />
          </Form.Item>
          {thresholdMode === 'parameter' ? (
            <Form.Item name="threshold_parameter" label="阈值参数名" rules={[{ required: true, whitespace: true }]}>
              <Input placeholder="如 allowable_load" maxLength={128} />
            </Form.Item>
          ) : (
            <Form.Item
              name="threshold_value"
              label="固定阈值"
              rules={[
                { required: true, whitespace: true },
                {
                  validator: async (_, value: string) => {
                    if (value != null && value !== '' && !Number.isFinite(Number(value))) throw new Error('阈值必须是数值')
                  },
                },
              ]}
            >
              <Input placeholder="支持小数，如 1.0" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </PageShell>
  )
}

function ExcelEtlGuide({ schemeTypeId }: { schemeTypeId?: number }) {
  const id = schemeTypeId ?? '<方案类型ID>'
  const previewCommand = `.\\.venv\\Scripts\\python.exe scripts\\import_rules_excel.py "D:\\path\\rules.xlsx" --scheme-type-id ${id} --report "D:\\path\\validation.json"`
  const applyCommand = `.\\.venv\\Scripts\\python.exe scripts\\import_rules_excel.py "D:\\path\\rules.xlsx" --scheme-type-id ${id} --apply --actor-id 1`

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        icon={<FileExcelOutlined />}
        message="当前后端未提供 Excel 上传 API，因此批量导入仅支持管理员在服务器命令行执行"
        description="脚本采用“先校验、后事务写入”的两阶段流程。任何一行有错误时都不会部分导入。请先运行预览命令并查看 JSON 报告，确认 valid=true 后再执行写入。"
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="1. 工作簿结构" size="small" style={{ height: '100%' }}>
            <Title level={5}>rules（或“规则”）工作表</Title>
            <Paragraph>
              必填列：<Text code>规则编号</Text>、<Text code>规则名称</Text>、<Text code>规则类型</Text>、
              <Text code>规则配置</Text>、<Text code>规范编号</Text>、<Text code>条款号</Text>、<Text code>条款原文</Text>。
            </Paragraph>
            <Title level={5}>formulas（或“公式”）工作表</Title>
            <Paragraph>
              公式规则才需要该表。常用列：<Text code>规则编号</Text>、<Text code>规则版本</Text>、
              <Text code>公式编号</Text>、<Text code>表达式</Text>、<Text code>变量映射</Text>、
              <Text code>比较符</Text>，以及<Text code>阈值</Text>或<Text code>阈值参数</Text>。
            </Paragraph>
            <Paragraph type="secondary">支持 .xlsx 和 .xlsm；JSON 单元格必须填写 JSON 对象。</Paragraph>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="2. 在 backend 目录运行" size="small" style={{ height: '100%' }}>
            <Text strong>预览与生成校验报告</Text>
            <Paragraph copyable={{ text: previewCommand }} code style={{ display: 'block', whiteSpace: 'pre-wrap', marginTop: 8 }}>
              {previewCommand}
            </Paragraph>
            <Text strong>校验通过后执行事务导入</Text>
            <Paragraph copyable={{ text: applyCommand }} code style={{ display: 'block', whiteSpace: 'pre-wrap', marginTop: 8 }}>
              {applyCommand}
            </Paragraph>
            <Alert
              type="warning"
              showIcon
              message="请勿直接使用 --replace-existing"
              description="覆盖已有版本会改变当前规则配置。若确需覆盖，应先备份并确认历史任务已保存配置快照。常规修改建议创建更高版本。"
            />
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
