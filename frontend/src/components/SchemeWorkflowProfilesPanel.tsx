import { ApiOutlined, DeleteOutlined, SaveOutlined } from '@ant-design/icons'
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
  Tag,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  DifyOutputFormat,
  SchemeType,
  SchemeWorkflowProfilePublic,
  SchemeWorkflowProfileUpdate,
} from '../api/types'
import { formatApiErrorMessage } from '../utils/apiError'

type CanonicalInput =
  | 'documents'
  | 'site_images'
  | 'project_name'
  | 'project_region'
  | 'risk_type'
  | 'review_focus'

type ProfileForm = {
  enabled: boolean
  base_url: string
  api_key?: string
  clear_api_key: boolean
  user_prefix: string
  timeout_seconds: number
  output_variable: string
  output_format: DifyOutputFormat
  accept_partial: boolean
  continue_on_failure: boolean
  input_mapping: Record<CanonicalInput, string>
}

const INPUT_FIELDS: Array<{
  key: CanonicalInput
  label: string
  description: string
  required?: boolean
}> = [
  {
    key: 'documents',
    label: '方案及附件',
    description: '主方案及补充资料文件数组；Dify 开始节点必须有对应文件变量。',
    required: true,
  },
  {
    key: 'site_images',
    label: '现场图片',
    description: '可选。留空时系统不会向 Dify 发送现场图片字段。',
  },
  { key: 'project_name', label: '项目名称', description: '项目名称或由文件名推导的名称。' },
  { key: 'project_region', label: '项目所在地', description: '用于地区法规和标准适用性判断。' },
  { key: 'risk_type', label: '危大工程类型', description: '由方案大类和方案名称组合生成。' },
  { key: 'review_focus', label: '审查重点', description: '本次审查重点与补充说明。' },
]

const LIFECYCLE_LABELS: Record<string, string> = {
  draft: '草稿',
  pending_validation: '待验证',
  published: '已发布',
  disabled: '已停用',
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message
  return formatApiErrorMessage(error, fallback)
}

function profileToForm(profile: SchemeWorkflowProfilePublic): ProfileForm {
  const mapping = profile.input_mapping ?? {}
  return {
    enabled: profile.enabled,
    base_url: profile.base_url,
    api_key: '',
    clear_api_key: false,
    user_prefix: profile.user_prefix || 'smart-review',
    timeout_seconds: profile.timeout_seconds,
    output_variable: profile.output_variable || 'report',
    output_format: profile.output_format,
    accept_partial: profile.accept_partial,
    continue_on_failure: profile.continue_on_failure,
    input_mapping: {
      documents: mapping.documents || 'documents',
      site_images: mapping.site_images || '',
      project_name: mapping.project_name || '',
      project_region: mapping.project_region || '',
      risk_type: mapping.risk_type || '',
      review_focus: mapping.review_focus || '',
    },
  }
}

export function SchemeWorkflowProfilesPanel() {
  const { message } = AntApp.useApp()
  const queryClient = useQueryClient()
  const [schemeId, setSchemeId] = useState<number | null>(null)
  const [form] = Form.useForm<ProfileForm>()
  const profileEnabled = Form.useWatch('enabled', form)
  const clearApiKey = Form.useWatch('clear_api_key', form)

  const schemesQuery = useQuery({
    queryKey: ['schemes'],
    queryFn: async () => {
      const { data } = await api.get<SchemeType[]>('/scheme-types', {
        params: { include_unpublished: true },
      })
      return data
    },
  })

  useEffect(() => {
    const rows = schemesQuery.data ?? []
    if (!rows.length) {
      setSchemeId(null)
      return
    }
    if (schemeId == null || !rows.some((item) => item.id === schemeId)) {
      setSchemeId(rows[0].id)
    }
  }, [schemeId, schemesQuery.data])

  const profileQuery = useQuery({
    queryKey: ['scheme-dify-profile', schemeId],
    queryFn: async () => {
      const { data } = await api.get<SchemeWorkflowProfilePublic>(
        `/scheme-types/${schemeId}/dify-workflow-profile`,
      )
      return data
    },
    enabled: schemeId != null,
    retry: false,
  })

  useEffect(() => {
    if (profileQuery.data) form.setFieldsValue(profileToForm(profileQuery.data))
  }, [form, profileQuery.data])

  const saveMutation = useMutation({
    mutationFn: async (values: ProfileForm) => {
      if (schemeId == null) throw new Error('请先选择方案类型')
      const key = values.api_key?.trim() || ''
      const canRetainExistingKey =
        profileQuery.data?.source === 'scheme_profile' &&
        profileQuery.data.api_key_configured &&
        !values.clear_api_key
      if (values.enabled && !key && !canRetainExistingKey) {
        throw new Error('启用类型专用 Workflow 时必须重新输入该应用的 API Key')
      }
      if (values.enabled && values.clear_api_key) {
        throw new Error('启用 Workflow 时不能同时清除 API Key；请先关闭启用开关')
      }
      const inputMapping = Object.fromEntries(
        INPUT_FIELDS.map(({ key: canonical }) => [
          canonical,
          values.input_mapping?.[canonical]?.trim() || '',
        ]).filter(([, target]) => Boolean(target)),
      )
      const payload: SchemeWorkflowProfileUpdate = {
        enabled: values.enabled,
        base_url: values.base_url.trim(),
        api_key: key || null,
        clear_api_key: values.clear_api_key,
        user_prefix: values.user_prefix.trim() || 'smart-review',
        timeout_seconds: values.timeout_seconds,
        output_variable: values.output_variable.trim(),
        output_format: values.output_format,
        accept_partial: values.accept_partial,
        continue_on_failure: values.continue_on_failure,
        input_mapping: inputMapping,
      }
      const { data } = await api.put<SchemeWorkflowProfilePublic>(
        `/scheme-types/${schemeId}/dify-workflow-profile`,
        payload,
      )
      return data
    },
    onSuccess: async (data) => {
      message.success('类型专用 Dify Profile 已保存；请重新验证并发布该方案类型')
      queryClient.setQueryData(['scheme-dify-profile', schemeId], data)
      await queryClient.invalidateQueries({ queryKey: ['schemes'] })
    },
    onError: (error) => message.error(errorText(error, 'Dify Profile 保存失败')),
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (schemeId == null) throw new Error('请先选择方案类型')
      const { data } = await api.delete<SchemeWorkflowProfilePublic>(
        `/scheme-types/${schemeId}/dify-workflow-profile`,
      )
      return data
    },
    onSuccess: async (data) => {
      message.success('类型专用配置已删除，当前恢复继承全局 Workflow 配置')
      queryClient.setQueryData(['scheme-dify-profile', schemeId], data)
      await queryClient.invalidateQueries({ queryKey: ['schemes'] })
    },
    onError: (error) => message.error(errorText(error, '删除类型专用配置失败')),
  })

  const profile = profileQuery.data
  const selectedScheme = schemesQuery.data?.find((item) => item.id === schemeId)
  const disableForm = schemeId == null || profileQuery.isLoading || !profile

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="warning"
        showIcon
        message="每种方案类型可以绑定不同的 Dify Workflow 应用"
        description="保存或删除类型专用 Profile 会使该类型的既有发布失效。完成配置后，请到“方案类型管理”重新提交验证并发布。密钥只写入服务端，不会在页面回显。"
      />

      <Card title={<Space><ApiOutlined />选择方案类型</Space>} loading={schemesQuery.isLoading}>
        {schemesQuery.isError ? (
          <Alert
            type="error"
            showIcon
            message="方案类型加载失败"
            description={formatApiErrorMessage(schemesQuery.error, '请检查服务状态后重试。')}
            action={<Button size="small" onClick={() => void schemesQuery.refetch()}>重试</Button>}
          />
        ) : (
          <Select
            showSearch
            optionFilterProp="label"
            style={{ width: '100%', maxWidth: 680 }}
            placeholder="请选择要配置的方案类型"
            value={schemeId ?? undefined}
            onChange={(value) => setSchemeId(value)}
            options={(schemesQuery.data ?? []).map((scheme) => ({
              value: scheme.id,
              label: `${scheme.category} / ${scheme.name}（${LIFECYCLE_LABELS[scheme.lifecycle_status] ?? scheme.lifecycle_status}）`,
            }))}
          />
        )}
      </Card>

      {profileQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="Dify Profile 加载失败"
          description={formatApiErrorMessage(profileQuery.error, '当前类型不存在，或账号没有管理权限。')}
          action={<Button size="small" onClick={() => void profileQuery.refetch()}>重试</Button>}
        />
      ) : null}

      <Card
        title="类型专用 Dify Workflow Profile"
        loading={profileQuery.isLoading}
        extra={
          profile ? (
            <Space wrap>
              <Tag color={profile.source === 'scheme_profile' ? 'blue' : 'default'}>
                {profile.source === 'scheme_profile' ? `类型专用 v${profile.version ?? '—'}` : '继承全局配置'}
              </Tag>
              <Tag color={profile.api_key_configured ? 'success' : 'warning'}>
                {profile.api_key_configured ? '密钥已配置' : '密钥未配置'}
              </Tag>
              {selectedScheme ? <Tag>{LIFECYCLE_LABELS[selectedScheme.lifecycle_status]}</Tag> : null}
            </Space>
          ) : null
        }
      >
        <Form<ProfileForm>
          form={form}
          layout="vertical"
          disabled={disableForm || saveMutation.isPending || deleteMutation.isPending}
          onFinish={(values) => saveMutation.mutate(values)}
        >
          <Row gutter={[16, 0]}>
            <Col xs={24} md={6}>
              <Form.Item name="enabled" label="启用类型专用 Workflow" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="关闭" />
              </Form.Item>
            </Col>
            <Col xs={24} md={18}>
              <Form.Item
                name="base_url"
                label="Workflow API 地址"
                rules={[
                  {
                    validator: async (_, value: string | undefined) => {
                      if (profileEnabled && !value?.trim()) {
                        throw new Error('启用类型专用 Workflow 时必须填写 API 地址')
                      }
                    },
                  },
                ]}
                extra="例如 http://100.72.36.25/v1；系统会自动去掉末尾斜杠。"
              >
                <Input placeholder="http://host/v1" autoComplete="off" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={[16, 0]}>
            <Col xs={24} md={16}>
              <Form.Item
                name="api_key"
                label="Workflow 应用 API Key"
                extra={
                  profile?.source === 'scheme_profile'
                    ? '留空表示保留该类型已保存的密钥；页面永不回显密钥明文。'
                    : '首次建立类型专用且启用的 Profile 时必须重新输入密钥；全局密钥不会被复制或回显。'
                }
              >
                <Input.Password
                  placeholder="app-…"
                  autoComplete="new-password"
                  disabled={Boolean(clearApiKey)}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="clear_api_key"
                label="清除类型专用密钥"
                valuePropName="checked"
                extra="仅清除本类型密钥；启用状态下不可清除。"
              >
                <Switch
                  checkedChildren="保存时清除"
                  unCheckedChildren="保留"
                  disabled={profile?.source !== 'scheme_profile' || !profile.api_key_configured}
                  onChange={(checked) => {
                    if (checked) form.setFieldValue('api_key', '')
                  }}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={[16, 0]}>
            <Col xs={24} md={8}>
              <Form.Item name="user_prefix" label="用户标识前缀" rules={[{ required: true, whitespace: true }]}>
                <Input placeholder="smart-review" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="timeout_seconds" label="最长等待（秒）" rules={[{ required: true }]}>
                <InputNumber min={30} max={3600} precision={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="output_variable" label="最终输出变量名" rules={[{ required: true, whitespace: true }]}>
                <Input placeholder="report" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={[16, 0]}>
            <Col xs={24} md={8}>
              <Form.Item name="output_format" label="输出格式" rules={[{ required: true }]}>
                <Select options={[
                  { value: 'json', label: '严格 JSON（推荐）' },
                  { value: 'auto', label: '自动识别' },
                  { value: 'markdown', label: 'Markdown 问题清单' },
                ]} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="accept_partial"
                label="接受 partly_succeeded"
                valuePropName="checked"
                extra="Dify 部分成功且输出存在时继续解析。"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="continue_on_failure"
                label="Dify 失败时保留本地结果"
                valuePropName="checked"
                extra="外部 Workflow 失败时任务降级，不抹掉本地规则结果。"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Divider titlePlacement="start">Dify 开始节点输入变量映射</Divider>
          <Typography.Paragraph type="secondary">
            左侧是系统标准字段，输入框填写该 Workflow 开始节点中的真实变量名。变量名只能包含字母、数字和下划线，且不能重复。
          </Typography.Paragraph>
          <Row gutter={[16, 0]}>
            {INPUT_FIELDS.map((field) => (
              <Col xs={24} md={12} key={field.key}>
                <Form.Item
                  name={['input_mapping', field.key]}
                  label={`${field.label}（${field.key}）`}
                  extra={field.description}
                  rules={field.required ? [
                    { required: true, whitespace: true, message: '方案文件变量必须映射' },
                    { pattern: /^[A-Za-z_][A-Za-z0-9_]*$/, message: '变量名格式不正确' },
                  ] : [
                    { pattern: /^[A-Za-z_][A-Za-z0-9_]*$/, message: '留空或填写合法变量名' },
                  ]}
                >
                  <Input placeholder={field.required ? field.key : '留空表示不发送'} />
                </Form.Item>
              </Col>
            ))}
          </Row>

          <Space wrap>
            <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saveMutation.isPending}>
              保存类型专用配置
            </Button>
            <Popconfirm
              title="删除类型专用配置？"
              description="删除后恢复继承全局 Workflow 配置，并使该类型的当前发布失效。"
              okText="确认删除"
              cancelText="取消"
              disabled={!profile?.configured}
              onConfirm={() => deleteMutation.mutate()}
            >
              <Button danger icon={<DeleteOutlined />} disabled={!profile?.configured} loading={deleteMutation.isPending}>
                删除并恢复全局配置
              </Button>
            </Popconfirm>
          </Space>
        </Form>
      </Card>
    </Space>
  )
}
