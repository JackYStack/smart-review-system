import {
  AppstoreOutlined,
  CheckCircleOutlined,
  PauseCircleOutlined,
  SendOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App as AntApp,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useState } from 'react'
import { api } from '../api/client'
import type { SchemeLifecycleStatus, SchemeReadinessStatus, SchemeType } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import PageShell from '../components/PageShell'
import { DEFAULT_TABLE_PAGINATION } from '../config/tablePagination'
import { formatApiErrorMessage } from '../utils/apiError'

type LifecycleAction = 'request-validation' | 'publish' | 'disable'

const LIFECYCLE_VIEW: Record<
  SchemeLifecycleStatus,
  { label: string; color: string }
> = {
  draft: { label: '草稿', color: 'default' },
  pending_validation: { label: '待验证', color: 'processing' },
  published: { label: '已发布', color: 'success' },
  disabled: { label: '已停用', color: 'error' },
}

const READINESS_VIEW: Record<
  SchemeReadinessStatus,
  { label: string; color: string }
> = {
  ready: { label: '已就绪', color: 'success' },
  incomplete: { label: '配置不完整', color: 'warning' },
  unavailable: { label: '不可用', color: 'error' },
}

const ACTION_SUCCESS: Record<LifecycleAction, string> = {
  'request-validation': '已提交验证，请根据就绪检查补齐配置后发布',
  publish: '方案类型已发布，可以在方案审核页提交任务',
  disable: '方案类型已停用，审核页将不再允许新任务',
}

function formatTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function extractPublishIssues(error: unknown): string[] {
  if (!axios.isAxiosError(error)) return []
  const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const issues = (detail as { readiness_issues?: unknown }).readiness_issues
    if (Array.isArray(issues)) {
      return issues.map((item) => String(item ?? '').trim()).filter(Boolean)
    }
  }
  if (typeof detail === 'string' && detail.trim()) return [detail.trim()]
  return []
}

export default function SchemesPage() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const { message, modal } = AntApp.useApp()
  const isAdmin = user?.role === 'admin'

  const {
    data = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['schemes'],
    queryFn: async () => {
      const { data: rows } = await api.get<SchemeType[]>('/scheme-types', {
        params: { include_unpublished: true },
      })
      return rows
    },
  })

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<SchemeType | null>(null)
  const [form] = Form.useForm()

  const saveMutation = useMutation({
    mutationFn: async (values: { category: string; name: string; remark?: string }) => {
      if (editing) {
        await api.patch(`/scheme-types/${editing.id}`, values)
      } else {
        await api.post('/scheme-types', values)
      }
    },
    onSuccess: async () => {
      message.success(editing ? '已保存；该类型已回到草稿状态，需重新验证发布' : '已创建草稿')
      setOpen(false)
      setEditing(null)
      form.resetFields()
      await qc.invalidateQueries({ queryKey: ['schemes'] })
    },
    onError: (mutationError) =>
      message.error(formatApiErrorMessage(mutationError, '保存失败')),
  })

  const lifecycleMutation = useMutation({
    mutationFn: async ({ id, action }: { id: number; action: LifecycleAction }) => {
      await api.post(`/scheme-types/${id}/${action}`, {
        comment: action === 'publish' ? '管理员确认发布' : '',
      })
    },
    onSuccess: async (_, variables) => {
      message.success(ACTION_SUCCESS[variables.action])
      await qc.invalidateQueries({ queryKey: ['schemes'] })
    },
    onError: (mutationError, variables) => {
      const issues = variables.action === 'publish' ? extractPublishIssues(mutationError) : []
      if (issues.length) {
        modal.error({
          title: '暂不能发布：仍有配置缺失',
          width: 620,
          content: (
            <div>
              <Typography.Paragraph type="secondary">
                请逐项补齐并重新提交验证。系统不会让未就绪的类型进入正式审核。
              </Typography.Paragraph>
              <ul style={{ marginBottom: 0, paddingInlineStart: 20 }}>
                {issues.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
              </ul>
            </div>
          ),
        })
        return
      }
      message.error(formatApiErrorMessage(mutationError, '生命周期操作失败'))
    },
  })

  const delMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/scheme-types/${id}`)
    },
    onSuccess: async () => {
      message.success('已删除')
      await qc.invalidateQueries({ queryKey: ['schemes'] })
    },
    onError: (mutationError) =>
      message.error(formatApiErrorMessage(mutationError, '删除失败')),
  })

  const lifecycleLoading = (row: SchemeType, action: LifecycleAction) =>
    lifecycleMutation.isPending &&
    lifecycleMutation.variables?.id === row.id &&
    lifecycleMutation.variables.action === action

  return (
    <PageShell
      icon={<AppstoreOutlined />}
      description="方案类型必须依次完成配置、提交验证和发布；只有“已发布且已就绪”的类型可创建正式审核任务。"
      extra={
        isAdmin ? (
          <Button
            type="primary"
            onClick={() => {
              setEditing(null)
              form.resetFields()
              setOpen(true)
            }}
          >
            新建方案类型
          </Button>
        ) : undefined
      }
    >
      {isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="方案类型加载失败"
          description={formatApiErrorMessage(error, '无法连接方案类型服务，请稍后重试。')}
          action={<Button size="small" onClick={() => void refetch()}>重试</Button>}
        />
      ) : null}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="发布是正式审核的准入开关"
        description="修改类型名称、模板、规则或分类型 Dify Profile 后，既有发布状态会自动失效，必须重新验证并发布。"
      />
      <Table<SchemeType>
        rowKey="id"
        size="middle"
        loading={isLoading}
        dataSource={data}
        locale={{ emptyText: '暂无方案类型' }}
        pagination={DEFAULT_TABLE_PAGINATION}
        scroll={{ x: 1320 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 72 },
          { title: '方案大类', dataIndex: 'category', width: 180 },
          { title: '方案名称', dataIndex: 'name', width: 240 },
          {
            title: '生命周期',
            key: 'lifecycle',
            width: 190,
            render: (_, row) => {
              const view = LIFECYCLE_VIEW[row.lifecycle_status] ?? {
                label: row.lifecycle_status,
                color: 'default',
              }
              return (
                <Space direction="vertical" size={4}>
                  <Tag color={view.color}>{view.label}</Tag>
                  {row.lifecycle_status === 'published' ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      发布时间：{formatTime(row.published_at)}
                      <br />模板版本：{row.published_template_version_id ? `#${row.published_template_version_id}` : '—'}
                    </Typography.Text>
                  ) : null}
                </Space>
              )
            },
          },
          {
            title: '就绪检查与缺失项',
            key: 'readiness',
            width: 360,
            render: (_, row) => {
              const view = READINESS_VIEW[row.readiness_status] ?? {
                label: row.readiness_status || '未知',
                color: 'default',
              }
              return (
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Tag color={view.color}>{view.label}</Tag>
                  {row.readiness_issues.length ? (
                    <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                      {row.readiness_issues.map((item, index) => (
                        <li key={`${index}-${item}`}>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            {item}
                          </Typography.Text>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      模板、规则、工作流及外部集成检查通过
                    </Typography.Text>
                  )}
                </Space>
              )
            },
          },
          { title: '备注', dataIndex: 'remark', width: 180, ellipsis: true },
          ...(isAdmin
            ? [
                {
                  title: '管理操作',
                  key: 'actions',
                  width: 330,
                  fixed: 'right' as const,
                  render: (_: unknown, row: SchemeType) => {
                    const validationDisabled =
                      row.lifecycle_status === 'pending_validation' || row.lifecycle_status === 'published'
                    const publishDisabled = row.lifecycle_status !== 'pending_validation'
                    return (
                      <Space wrap size="small">
                        <Tooltip title={row.lifecycle_status === 'published' ? '修改后将撤销发布，需重新验证' : undefined}>
                          <Button
                            type="link"
                            size="small"
                            onClick={() => {
                              setEditing(row)
                              form.setFieldsValue({
                                category: row.category,
                                name: row.name,
                                remark: row.remark ?? '',
                              })
                              setOpen(true)
                            }}
                          >
                            编辑
                          </Button>
                        </Tooltip>
                        <Tooltip title={validationDisabled ? '当前状态无需重复提交验证' : undefined}>
                          <Button
                            size="small"
                            icon={<SendOutlined />}
                            disabled={validationDisabled}
                            loading={lifecycleLoading(row, 'request-validation')}
                            onClick={() => lifecycleMutation.mutate({ id: row.id, action: 'request-validation' })}
                          >
                            提交验证
                          </Button>
                        </Tooltip>
                        <Tooltip title={publishDisabled ? '请先提交验证' : row.readiness_status !== 'ready' ? '点击可查看具体缺失项' : undefined}>
                          <Button
                            type="primary"
                            size="small"
                            icon={<CheckCircleOutlined />}
                            disabled={publishDisabled}
                            loading={lifecycleLoading(row, 'publish')}
                            onClick={() => lifecycleMutation.mutate({ id: row.id, action: 'publish' })}
                          >
                            发布
                          </Button>
                        </Tooltip>
                        <Popconfirm
                          title="停用该方案类型？"
                          description="停用后不能再提交新审核任务，历史任务不受影响。"
                          okText="确认停用"
                          cancelText="取消"
                          disabled={row.lifecycle_status === 'disabled'}
                          onConfirm={() => lifecycleMutation.mutate({ id: row.id, action: 'disable' })}
                        >
                          <Button
                            danger
                            size="small"
                            icon={<PauseCircleOutlined />}
                            disabled={row.lifecycle_status === 'disabled'}
                            loading={lifecycleLoading(row, 'disable')}
                          >
                            停用
                          </Button>
                        </Popconfirm>
                        <Tooltip title={row.lifecycle_status === 'published' ? '请先停用，再删除' : undefined}>
                          <Popconfirm
                            title="确定永久删除？"
                            description="该操作不可恢复。"
                            disabled={row.lifecycle_status === 'published'}
                            onConfirm={() => delMutation.mutate(row.id)}
                          >
                            <Button type="link" size="small" danger disabled={row.lifecycle_status === 'published'}>
                              删除
                            </Button>
                          </Popconfirm>
                        </Tooltip>
                      </Space>
                    )
                  },
                },
              ]
            : []),
        ]}
      />
      <Modal
        title={editing ? '编辑方案类型' : '新建方案类型'}
        open={open}
        onCancel={() => {
          setOpen(false)
          setEditing(null)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        confirmLoading={saveMutation.isPending}
        destroyOnClose
      >
        {editing?.lifecycle_status === 'published' ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            message="保存修改后会撤销当前发布状态"
            description="请在配置复核完成后重新执行“提交验证 → 发布”。"
          />
        ) : null}
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => saveMutation.mutate(values)}
          initialValues={{ category: '', remark: '' }}
        >
          <Form.Item
            name="category"
            label="方案大类"
            rules={[{ required: true, whitespace: true, message: '请输入方案大类' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="name" label="方案名称" rules={[{ required: true, whitespace: true, message: '请输入方案名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  )
}
