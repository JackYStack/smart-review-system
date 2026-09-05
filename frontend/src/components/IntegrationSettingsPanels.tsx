import {
  ApiOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  ReloadOutlined,
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
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  DifyOutputFormat,
  ConfigurationAudit,
  ConfigurationHistory,
  IntegrationSettings,
  IntegrationTestResult,
  ServiceStatus,
} from '../api/types'

type IntegrationForm = {
  dify_workflow_enabled: boolean
  dify_workflow_base_url: string
  dify_workflow_api_key?: string
  dify_workflow_user_prefix: string
  dify_workflow_timeout_seconds: number
  dify_workflow_output_variable: string
  dify_workflow_output_format: DifyOutputFormat
  dify_workflow_accept_partial: boolean
  dify_workflow_continue_on_failure: boolean
  paddleocr_api_url: string
  paddleocr_api_key?: string
  paddleocr_timeout_seconds: number
  paddle_convert_timeout_seconds: number
}

const sourceLabel = {
  database: '设置页覆盖',
  environment: '环境变量兜底',
  default: '系统默认值',
} as const

const stateView = {
  connected: { color: 'success', text: '连接正常' },
  configured: { color: 'processing', text: '已配置' },
  unconfigured: { color: 'default', text: '未配置' },
  error: { color: 'error', text: '连接异常' },
} as const

const testableServices = new Set([
  'dify_workflow',
  'dify_dataset',
  'paddleocr',
  'libreoffice',
  'onlyoffice',
  'minio',
])

const fieldLabels: Record<string, string> = {
  dify_workflow_enabled: 'Workflow启用状态',
  dify_workflow_base_url: 'Workflow API地址',
  dify_workflow_api_key: 'Workflow应用密钥',
  dify_workflow_user_prefix: '用户标识前缀',
  dify_workflow_timeout_seconds: 'Workflow超时',
  dify_workflow_output_variable: '输出变量名',
  dify_workflow_output_format: '输出格式',
  dify_workflow_accept_partial: '接受部分成功',
  dify_workflow_continue_on_failure: '失败继续策略',
  paddleocr_api_url: 'PaddleOCR地址',
  paddleocr_api_key: 'PaddleOCR密钥',
  paddleocr_timeout_seconds: 'OCR超时',
  paddle_convert_timeout_seconds: '文档转换超时',
}

export function ServiceStatusPanel() {
  const { message } = AntApp.useApp()
  const [results, setResults] = useState<Record<string, IntegrationTestResult>>({})
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['settings', 'services', 'status'],
    queryFn: async () => {
      const response = await api.get<ServiceStatus>('/settings/services/status')
      return response.data
    },
  })
  const testMut = useMutation({
    mutationFn: async (service: string) => {
      const response = await api.post<IntegrationTestResult>('/settings/integrations/test', {
        service,
      })
      return response.data
    },
    onSuccess: (result) => {
      setResults((current) => ({ ...current, [result.service]: result }))
      if (result.ok) message.success(`${result.service} 连接正常`)
      else message.error(result.detail)
    },
    onError: () => message.error('连接测试请求失败'),
  })

  const downloadDiagnostics = async () => {
    try {
      const response = await api.get('/settings/diagnostics/download', { responseType: 'blob' })
      const href = URL.createObjectURL(response.data as Blob)
      const link = document.createElement('a')
      link.href = href
      link.download = `smartreview-diagnostics-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(href)
      message.success('已生成脱敏诊断报告')
    } catch {
      message.error('诊断报告生成失败')
    }
  }

  return (
    <Card
      title="服务状态概览"
      loading={isLoading}
      extra={
        <Space>
          <Button icon={<DownloadOutlined />} onClick={() => void downloadDiagnostics()}>
            下载脱敏诊断
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => void refetch()}>
            刷新状态
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        message="状态说明"
        description="“已配置”表示参数齐全；点击测试连接后才能确认远端服务当前可用。MySQL等部署级服务只提供诊断，不在网页中修改凭据。"
        style={{ marginBottom: 16 }}
      />
      <Row gutter={[16, 16]}>
        {(data?.services ?? []).map((item) => {
          const latest = results[item.service]
          const view = latest
            ? latest.ok
              ? stateView.connected
              : stateView.error
            : stateView[item.state]
          return (
            <Col xs={24} md={12} xl={8} key={item.service}>
              <Card size="small" style={{ height: '100%' }}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text strong>{item.label}</Typography.Text>
                    <Tag color={view.color}>{view.text}</Tag>
                  </Space>
                  <Typography.Text type="secondary">
                    {latest?.detail ?? item.detail}
                  </Typography.Text>
                  {latest?.latency_ms != null && (
                    <Typography.Text type="secondary">
                      响应耗时：{latest.latency_ms} ms
                    </Typography.Text>
                  )}
                  {testableServices.has(item.service) && (
                    <Button
                      size="small"
                      icon={<ApiOutlined />}
                      loading={testMut.isPending && testMut.variables === item.service}
                      onClick={() => testMut.mutate(item.service)}
                    >
                      测试连接
                    </Button>
                  )}
                </Space>
              </Card>
            </Col>
          )
        })}
      </Row>
    </Card>
  )
}

export function IntegrationSettingsPanel() {
  const { message } = AntApp.useApp()
  const queryClient = useQueryClient()
  const [form] = Form.useForm<IntegrationForm>()
  const { data, isLoading } = useQuery({
    queryKey: ['settings', 'integrations'],
    queryFn: async () => {
      const response = await api.get<IntegrationSettings>('/settings/integrations')
      return response.data
    },
  })
  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['settings', 'integrations', 'history'],
    queryFn: async () => {
      const response = await api.get<ConfigurationHistory>('/settings/integrations/history')
      return response.data
    },
  })

  useEffect(() => {
    if (!data) return
    form.setFieldsValue({
      dify_workflow_enabled: data.workflow.enabled,
      dify_workflow_base_url: data.workflow.base_url,
      dify_workflow_api_key: '',
      dify_workflow_user_prefix: data.workflow.user_prefix,
      dify_workflow_timeout_seconds: data.workflow.timeout_seconds,
      dify_workflow_output_variable: data.workflow.output_variable,
      dify_workflow_output_format: data.workflow.output_format,
      dify_workflow_accept_partial: data.workflow.accept_partial,
      dify_workflow_continue_on_failure: data.workflow.continue_on_failure,
      paddleocr_api_url: data.document.paddleocr_api_url,
      paddleocr_api_key: '',
      paddleocr_timeout_seconds: data.document.paddleocr_timeout_seconds,
      paddle_convert_timeout_seconds: data.document.convert_timeout_seconds,
    })
  }, [data, form])

  const saveMut = useMutation({
    mutationFn: async (values: IntegrationForm) => {
      const payload = {
        ...values,
        dify_workflow_base_url: values.dify_workflow_base_url.trim(),
        dify_workflow_user_prefix: values.dify_workflow_user_prefix.trim(),
        dify_workflow_output_variable: values.dify_workflow_output_variable.trim(),
        paddleocr_api_url: values.paddleocr_api_url.trim(),
        dify_workflow_api_key: values.dify_workflow_api_key?.trim() || undefined,
        paddleocr_api_key: values.paddleocr_api_key?.trim() || undefined,
      }
      await api.put('/settings/integrations', payload)
    },
    onSuccess: async () => {
      message.success('集成服务配置已保存，仅对新任务生效')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['settings', 'integrations'] }),
        queryClient.invalidateQueries({ queryKey: ['settings', 'services', 'status'] }),
        queryClient.invalidateQueries({ queryKey: ['settings', 'integrations', 'history'] }),
      ])
    },
    onError: () => message.error('保存失败，请检查字段格式'),
  })

  const rollbackMut = useMutation({
    mutationFn: async (auditId: number) => {
      await api.post(`/settings/integrations/history/${auditId}/rollback`)
    },
    onSuccess: async () => {
      message.success('配置已回滚，仅对新任务生效')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['settings', 'integrations'] }),
        queryClient.invalidateQueries({ queryKey: ['settings', 'integrations', 'history'] }),
        queryClient.invalidateQueries({ queryKey: ['settings', 'services', 'status'] }),
      ])
    },
    onError: () => message.error('回滚失败'),
  })

  const quickTest = useMutation({
    mutationFn: async (service: string) => {
      const response = await api.post<IntegrationTestResult>('/settings/integrations/test', {
        service,
      })
      return response.data
    },
    onSuccess: (result) => {
      if (result.ok) message.success(result.detail)
      else message.error(result.detail)
    },
    onError: () => message.error('连接测试请求失败'),
  })

  return (
    <Form<IntegrationForm>
      form={form}
      layout="vertical"
      onFinish={(values) => saveMut.mutate(values)}
      initialValues={{
        dify_workflow_enabled: false,
        dify_workflow_output_format: 'auto',
        dify_workflow_accept_partial: true,
        dify_workflow_continue_on_failure: true,
      }}
    >
      <Card
        title={
          <Space>
            <DatabaseOutlined />
            Dify Workflow
          </Space>
        }
        loading={isLoading}
        extra={
          <Tag color="blue">
            {sourceLabel[data?.workflow.source ?? 'environment']}
          </Tag>
        }
      >
        <Alert
          type="warning"
          showIcon
          message="Workflow应用密钥与Dataset知识库密钥不是同一种密钥"
          description="这里填写发布Workflow应用后获得的 app- 密钥。密钥不会回显，输入框留空表示保留当前密钥。"
          style={{ marginBottom: 16 }}
        />
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item label="启用全文审查" name="dify_workflow_enabled" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          </Col>
          <Col xs={24} md={16}>
            <Form.Item
              label="Workflow API地址"
              name="dify_workflow_base_url"
              rules={[{ required: true, message: '请输入完整API地址' }]}
              extra="例如 http://100.x.x.x/v1"
            >
              <Input placeholder="http://host/v1" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              label={`应用API密钥（${data?.workflow.api_key_configured ? '已配置' : '未配置'}）`}
              name="dify_workflow_api_key"
              extra="留空表示不修改"
            >
              <Input.Password placeholder="app-..." autoComplete="new-password" />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item label="用户标识前缀" name="dify_workflow_user_prefix">
              <Input placeholder="smart-review" />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item label="最长等待（秒）" name="dify_workflow_timeout_seconds">
              <InputNumber min={30} max={3600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="最终输出变量名" name="dify_workflow_output_variable">
              <Input placeholder="report" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="输出内容格式" name="dify_workflow_output_format">
              <Select
                options={[
                  { value: 'auto', label: '自动识别（推荐）' },
                  { value: 'json', label: '严格JSON' },
                  { value: 'markdown', label: 'Markdown问题清单' },
                ]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={4}>
            <Form.Item label="接受部分成功" name="dify_workflow_accept_partial" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={4}>
            <Form.Item label="失败时继续本地结果" name="dify_workflow_continue_on_failure" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        </Row>
        <Button
          icon={<CheckCircleOutlined />}
          loading={quickTest.isPending && quickTest.variables === 'dify_workflow'}
          onClick={() => quickTest.mutate('dify_workflow')}
        >
          测试当前已保存配置
        </Button>
      </Card>

      <Divider />

      <Card
        title={
          <Space>
            <FileSearchOutlined />
            文档解析服务
          </Space>
        }
        loading={isLoading}
        extra={<Tag color="blue">{sourceLabel[data?.document.source ?? 'environment']}</Tag>}
      >
        <Row gutter={16}>
          <Col xs={24} md={14}>
            <Form.Item
              label="PaddleOCR接口地址"
              name="paddleocr_api_url"
              rules={[{ required: true, message: '请输入PaddleOCR接口地址' }]}
            >
              <Input placeholder="http://host:8080/layout-parsing" />
            </Form.Item>
          </Col>
          <Col xs={24} md={10}>
            <Form.Item
              label={`PaddleOCR密钥（${data?.document.paddleocr_api_key_configured ? '已配置' : '未配置/无需密钥'}）`}
              name="paddleocr_api_key"
              extra="留空表示不修改"
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="OCR解析超时（秒）" name="paddleocr_timeout_seconds">
              <InputNumber min={10} max={3600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="Word转PDF超时（秒）" name="paddle_convert_timeout_seconds">
              <InputNumber min={10} max={1200} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Typography.Text type="secondary">
              LibreOffice：{data?.document.libreoffice_configured ? '已检测到' : '未检测到'}
            </Typography.Text>
          </Col>
        </Row>
        <Space wrap>
          <Button
            icon={<CheckCircleOutlined />}
            loading={quickTest.isPending && quickTest.variables === 'paddleocr'}
            onClick={() => quickTest.mutate('paddleocr')}
          >
            测试PaddleOCR
          </Button>
          <Button
            icon={<CheckCircleOutlined />}
            loading={quickTest.isPending && quickTest.variables === 'libreoffice'}
            onClick={() => quickTest.mutate('libreoffice')}
          >
            检测LibreOffice
          </Button>
        </Space>
      </Card>

      <Space style={{ marginTop: 16 }}>
        <Button type="primary" htmlType="submit" loading={saveMut.isPending}>
          保存集成配置
        </Button>
        <Typography.Text type="secondary">保存后仅对新提交的审核任务生效</Typography.Text>
      </Space>

      <Divider />

      <Card
        title={
          <Space>
            <HistoryOutlined />
            配置修改历史
          </Space>
        }
      >
        <Alert
          type="info"
          showIcon
          message="历史记录不保存密钥明文"
          description="回滚会生成新的历史版本，不会删除原记录；回滚后的配置只对新任务生效。"
          style={{ marginBottom: 16 }}
        />
        <Table<ConfigurationAudit>
          rowKey="id"
          size="small"
          loading={historyLoading}
          dataSource={historyData?.items ?? []}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          locale={{ emptyText: '暂无修改历史' }}
          columns={[
            {
              title: '时间',
              dataIndex: 'created_at',
              width: 180,
              render: (value: string | null) => value?.replace('T', ' ').slice(0, 19) || '—',
            },
            { title: '操作人', dataIndex: 'actor_username', width: 120 },
            {
              title: '操作',
              dataIndex: 'action',
              width: 130,
              render: (value: string) => (value.startsWith('rollback:') ? '回滚' : '保存配置'),
            },
            {
              title: '变更内容',
              dataIndex: 'changed_fields',
              render: (fields: string[]) =>
                fields.length ? fields.map((field) => fieldLabels[field] ?? field).join('、') : '无字段变化',
            },
            {
              title: '操作',
              key: 'rollback',
              width: 100,
              render: (_: unknown, row: ConfigurationAudit) => (
                <Popconfirm
                  title="回滚到此次修改之前？"
                  description="回滚后仅影响新任务，并会保留新的审计记录。"
                  okText="确认回滚"
                  cancelText="取消"
                  onConfirm={() => rollbackMut.mutate(row.id)}
                >
                  <Button type="link" size="small" disabled={!row.can_rollback}>
                    回滚
                  </Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>
    </Form>
  )
}
