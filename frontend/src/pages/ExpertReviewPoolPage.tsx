import {
  AuditOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { ExpertReviewRound } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import PageShell from '../components/PageShell'
import { DEFAULT_TABLE_PAGINATION } from '../config/tablePagination'
import { formatApiErrorMessage } from '../utils/apiError'
import {
  COMPLETENESS_LABELS,
  REVIEW_CONCLUSION_LABELS,
  REVIEW_MANAGER_ROLES,
  canClaimRound,
  claimIsActive,
  formatReviewTime,
  roundStatusMeta,
} from '../utils/expertReview'

const STATUS_OPTIONS = [
  { label: '等待AI审查', value: 'pending_ai' },
  { label: '待领取', value: 'pending' },
  { label: '复核中', value: 'in_review' },
  { label: '已退回整改', value: 'changes_requested' },
  { label: '等待复审版本', value: 'pending_recheck' },
  { label: '已批准待签发', value: 'approved' },
  { label: '已签发', value: 'signed' },
]

export default function ExpertReviewPoolPage() {
  const { user } = useAuth()
  const { message } = AntApp.useApp()
  const nav = useNavigate()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [assignedToMe, setAssignedToMe] = useState(false)
  const [availableOnly, setAvailableOnly] = useState(false)
  const isManager = Boolean(user && REVIEW_MANAGER_ROLES.has(user.role))

  const roundsQuery = useQuery({
    queryKey: ['expert-review-rounds', statusFilter ?? '', assignedToMe, availableOnly],
    queryFn: async () => {
      const { data } = await api.get<ExpertReviewRound[]>('/expert/review-rounds', {
        params: {
          status: statusFilter || undefined,
          assigned_to_me: assignedToMe,
          available_only: availableOnly,
          limit: 500,
        },
      })
      return data
    },
    refetchInterval: (query) =>
      query.state.data?.some((row) => row.status === 'pending_ai' || row.status === 'in_review')
        ? 10_000
        : false,
  })

  const syncMut = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ created: number }>('/expert/review-rounds/sync')
      return data
    },
    onSuccess: async (data) => {
      message.success(data.created > 0 ? `已新增 ${data.created} 个复核任务` : '复核任务已是最新')
      await queryClient.invalidateQueries({ queryKey: ['expert-review-rounds'] })
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '同步复核任务失败')),
  })

  const claimMut = useMutation({
    mutationFn: async (roundId: number) => {
      const { data } = await api.post<ExpertReviewRound>(
        `/expert/review-rounds/${roundId}/claim`,
      )
      return data
    },
    onSuccess: async (data) => {
      message.success('任务领取成功')
      await queryClient.invalidateQueries({ queryKey: ['expert-review-rounds'] })
      nav(`/expert-reviews/${data.id}`)
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '领取失败')),
  })

  const rounds = useMemo(() => roundsQuery.data ?? [], [roundsQuery.data])
  const stats = useMemo(
    () => ({
      total: rounds.length,
      available: rounds.filter((row) => row.status === 'pending' && !row.assigned_expert_id).length,
      inReview: rounds.filter((row) => row.status === 'in_review').length,
      signed: rounds.filter((row) => row.status === 'signed').length,
    }),
    [rounds],
  )

  return (
    <PageShell
      icon={<SafetyCertificateOutlined />}
      description="专家在此领取AI审查结果，逐项核验证据并形成可追溯的人工复核与签发结论。"
      extra={
        <Space wrap>
          <Button
            icon={<ReloadOutlined />}
            loading={roundsQuery.isFetching}
            onClick={() => void roundsQuery.refetch()}
          >
            刷新
          </Button>
          {isManager ? (
            <Button
              type="primary"
              icon={<UserSwitchOutlined />}
              loading={syncMut.isPending}
              onClick={() => syncMut.mutate()}
            >
              同步审核任务
            </Button>
          ) : null}
        </Space>
      }
    >
      {roundsQuery.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="专家复核任务加载失败"
          description={formatApiErrorMessage(
            roundsQuery.error,
            '当前账号可能没有专家复核权限，或后端服务暂不可用。',
          )}
          action={<Button size="small" onClick={() => void roundsQuery.refetch()}>重试</Button>}
        />
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 16 }}>
        <Card size="small"><Statistic title="当前列表" value={stats.total} prefix={<AuditOutlined />} /></Card>
        <Card size="small"><Statistic title="可领取" value={stats.available} prefix={<ClockCircleOutlined />} /></Card>
        <Card size="small"><Statistic title="复核中" value={stats.inReview} prefix={<UserSwitchOutlined />} /></Card>
        <Card size="small"><Statistic title="已签发" value={stats.signed} prefix={<CheckCircleOutlined />} /></Card>
      </div>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size="large">
          <Select
            allowClear
            placeholder="全部复核状态"
            style={{ minWidth: 180 }}
            options={STATUS_OPTIONS}
            value={statusFilter}
            onChange={setStatusFilter}
          />
          <Space>
            <Switch
              checked={assignedToMe}
              onChange={(checked) => {
                setAssignedToMe(checked)
                if (checked) setAvailableOnly(false)
              }}
            />
            <span>只看我领取的</span>
          </Space>
          <Space>
            <Switch
              checked={availableOnly}
              onChange={(checked) => {
                setAvailableOnly(checked)
                if (checked) setAssignedToMe(false)
              }}
            />
            <span>只看可领取任务</span>
          </Space>
        </Space>
      </Card>

      <Table<ExpertReviewRound>
        rowKey="id"
        loading={roundsQuery.isLoading}
        dataSource={rounds}
        pagination={DEFAULT_TABLE_PAGINATION}
        locale={{ emptyText: roundsQuery.isError ? '加载失败，请重试' : '暂无符合条件的复核任务' }}
        scroll={{ x: 1700 }}
        columns={[
          { title: '复核ID', dataIndex: 'id', width: 88 },
          { title: '轮次', dataIndex: 'round_no', width: 72, render: (v: number) => `第${v}轮` },
          {
            title: '复核状态',
            dataIndex: 'status',
            width: 132,
            render: (value: string) => {
              const meta = roundStatusMeta(value)
              return <Tag color={meta.color}>{meta.label}</Tag>
            },
          },
          {
            title: '方案类型',
            key: 'scheme',
            width: 230,
            ellipsis: true,
            render: (_, row) => `${row.scheme_category} / ${row.scheme_name}`,
          },
          {
            title: '项目/版本',
            key: 'project',
            width: 220,
            render: (_, row) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.project_name?.trim() || '历史任务未关联项目'}</Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {[row.project_region?.trim(), row.version_label?.trim()].filter(Boolean).join(' · ') || '—'}
                </Typography.Text>
              </Space>
            ),
          },
          {
            title: '文件',
            dataIndex: 'original_filename',
            width: 220,
            ellipsis: { showTitle: false },
            render: (value: string) => <Tooltip title={value}><Typography.Text ellipsis>{value}</Typography.Text></Tooltip>,
          },
          { title: '提交人', dataIndex: 'task_owner_username', width: 110 },
          {
            title: 'AI结论',
            dataIndex: 'review_conclusion',
            width: 120,
            render: (value: string) => REVIEW_CONCLUSION_LABELS[value] ?? value ?? '—',
          },
          {
            title: '完整性',
            dataIndex: 'completeness_status',
            width: 112,
            render: (value: string) => (
              <Tag color={value === 'complete' ? 'success' : value === 'unavailable' ? 'error' : 'warning'}>
                {COMPLETENESS_LABELS[value] ?? value ?? '—'}
              </Tag>
            ),
          },
          {
            title: '问题处置',
            key: 'issues',
            width: 120,
            render: (_, row) => `${row.issue_count - row.pending_issue_count}/${row.issue_count}`,
          },
          {
            title: '领取专家',
            dataIndex: 'assigned_expert_username',
            width: 120,
            render: (value: string | null) => value || '未领取',
          },
          {
            title: '领取有效期',
            dataIndex: 'claim_expires_at',
            width: 180,
            render: formatReviewTime,
          },
          {
            title: '操作',
            key: 'actions',
            width: 190,
            fixed: 'right',
            render: (_, row) => {
              const assignedToCurrentUser = row.assigned_expert_id === user?.id
              const claimable =
                canClaimRound(row) &&
                (!row.assigned_expert_id || assignedToCurrentUser || !claimIsActive(row))
              return (
                <Space size="small">
                  <Button type="link" size="small" onClick={() => nav(`/expert-reviews/${row.id}`)}>
                    查看详情
                  </Button>
                  {claimable && (!row.assigned_expert_id || !claimIsActive(row)) ? (
                    <Button
                      type="link"
                      size="small"
                      loading={claimMut.isPending && claimMut.variables === row.id}
                      onClick={() => claimMut.mutate(row.id)}
                    >
                      {row.assigned_expert_id ? '重新领取' : '领取'}
                    </Button>
                  ) : null}
                </Space>
              )
            },
          },
        ]}
      />
    </PageShell>
  )
}
