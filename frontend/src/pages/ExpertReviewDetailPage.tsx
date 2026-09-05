import {
  ArrowLeftOutlined,
  CheckOutlined,
  CloseOutlined,
  DownloadOutlined,
  EditOutlined,
  EyeOutlined,
  FileProtectOutlined,
  LockOutlined,
  RollbackOutlined,
  UnlockOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Collapse,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Timeline,
  Tooltip,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type {
  AuditEventPublic,
  ExpertReviewConclusion,
  ExpertReviewIssue,
  ExpertReviewRoundDetail,
  IssueDisposition,
  ReviewSourceDownload,
  SignedReportDownload,
} from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { formatApiErrorMessage } from '../utils/apiError'
import { buildReviewExportFilename } from '../utils/reviewExportFilename'
import {
  COMPLETENESS_LABELS,
  DISPOSITION_META,
  REVIEW_CONCLUSION_LABELS,
  REVIEW_MANAGER_ROLES,
  SEVERITY_META,
  STEP_LABELS,
  formatReviewTime,
  claimIsActive,
  hasIssueLocation,
  issueLocationText,
  roundStatusMeta,
} from '../utils/expertReview'
import { translateReviewMetadata } from '../utils/reviewDisplay'

type IssueDecisionForm = {
  disposition: IssueDisposition
  final_severity?: 'error' | 'warning' | 'info'
  reviewer_comment: string
}

type RoundActionMode = 'request_changes' | 'approve'
type RoundActionForm = {
  conclusion: ExpertReviewConclusion
  comment: string
}

const DECISION_ACTION_LABELS: Record<string, string> = {
  round_created: '创建复核任务',
  ai_review_finished: 'AI审核完成',
  claimed: '领取任务',
  released: '释放任务',
  issue_decided: '处置问题',
  request_changes: '退回整改',
  approve: '批准复核',
  signed: '签发报告',
  revision_submitted: '提交整改版本',
}

function extractSuggestions(related: Record<string, unknown>): string[] {
  const values = [related.suggestions, related.suggestion]
  const output: string[] = []
  for (const value of values) {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        const text = String(item ?? '').trim()
        if (text) output.push(text)
      })
    } else {
      const text = String(value ?? '').trim()
      if (text) output.push(text)
    }
  }
  return Array.from(new Set(output))
}

function issueEvidenceIsVerified(issue: ExpertReviewIssue): boolean {
  return String(issue.related.evidence_status ?? '').trim().toLowerCase() === 'verified'
}

async function downloadFromUrl(url: string, filename: string): Promise<void> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`文件下载失败（HTTP ${response.status}）`)
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

export default function ExpertReviewDetailPage() {
  const { roundId } = useParams<{ roundId: string }>()
  const id = Number(roundId)
  const nav = useNavigate()
  const { user } = useAuth()
  const { message } = AntApp.useApp()
  const queryClient = useQueryClient()
  const isManager = Boolean(user && REVIEW_MANAGER_ROLES.has(user.role))
  const [issueEditing, setIssueEditing] = useState<ExpertReviewIssue | null>(null)
  const [issueForm] = Form.useForm<IssueDecisionForm>()
  const [releaseOpen, setReleaseOpen] = useState(false)
  const [releaseComment, setReleaseComment] = useState('')
  const [roundAction, setRoundAction] = useState<RoundActionMode | null>(null)
  const [roundActionForm] = Form.useForm<RoundActionForm>()

  const detailQuery = useQuery({
    queryKey: ['expert-review-round', id],
    queryFn: async () => {
      const { data } = await api.get<ExpertReviewRoundDetail>(`/expert/review-rounds/${id}`)
      return data
    },
    enabled: Number.isFinite(id) && id > 0,
    refetchInterval: (query) =>
      query.state.data?.status === 'pending_ai' || query.state.data?.status === 'in_review'
        ? 10_000
        : false,
  })

  const auditQuery = useQuery({
    queryKey: ['expert-audit-events', id],
    queryFn: async () => {
      const { data } = await api.get<AuditEventPublic[]>('/expert/audit-events', {
        params: { entity_type: 'review_round', entity_id: String(id), limit: 500 },
      })
      return data
    },
    enabled: Number.isFinite(id) && id > 0 && isManager,
    retry: false,
  })

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['expert-review-round', id] }),
      queryClient.invalidateQueries({ queryKey: ['expert-review-rounds'] }),
      queryClient.invalidateQueries({ queryKey: ['expert-audit-events', id] }),
    ])
  }

  const claimMut = useMutation({
    mutationFn: async () => api.post(`/expert/review-rounds/${id}/claim`),
    onSuccess: async () => {
      message.success('任务已领取，可以开始逐项复核')
      await invalidate()
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '领取失败')),
  })

  const releaseMut = useMutation({
    mutationFn: async (comment: string) =>
      api.post(`/expert/review-rounds/${id}/release`, { comment }),
    onSuccess: async () => {
      message.success('任务已释放回任务池')
      setReleaseOpen(false)
      setReleaseComment('')
      await invalidate()
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '释放失败')),
  })

  const issueMut = useMutation({
    mutationFn: async ({ issueId, values }: { issueId: number; values: IssueDecisionForm }) => {
      const { data } = await api.patch<ExpertReviewIssue>(
        `/expert/review-rounds/${id}/issues/${issueId}`,
        {
          disposition: values.disposition,
          reviewer_comment: values.reviewer_comment?.trim() || '',
          final_severity: values.final_severity || null,
        },
      )
      return data
    },
    onSuccess: async () => {
      message.success('问题处置已保存')
      setIssueEditing(null)
      issueForm.resetFields()
      await invalidate()
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '问题处置失败')),
  })

  const roundActionMut = useMutation({
    mutationFn: async ({ mode, values }: { mode: RoundActionMode; values: RoundActionForm }) => {
      const endpoint = mode === 'approve' ? 'approve' : 'request-changes'
      await api.post(`/expert/review-rounds/${id}/${endpoint}`, {
        conclusion: values.conclusion,
        comment: values.comment?.trim() || '',
      })
    },
    onSuccess: async (_, variables) => {
      message.success(variables.mode === 'approve' ? '复核已批准' : '已退回整改')
      setRoundAction(null)
      roundActionForm.resetFields()
      await invalidate()
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '复核状态更新失败')),
  })

  const signMut = useMutation({
    mutationFn: async () => api.post(`/expert/review-rounds/${id}/sign`),
    onSuccess: async () => {
      message.success('正式复核报告已签发')
      await invalidate()
    },
    onError: (error) => message.error(formatApiErrorMessage(error, '签发失败')),
  })

  const downloadAiDocumentMut = useMutation({
    mutationFn: async () => {
      const round = detailQuery.data
      if (!round) throw new Error('复核任务尚未加载')
      const { data } = await api.get<{ url: string }>(
        `/review-tasks/${round.task_id}/output-download-url`,
      )
      await downloadFromUrl(data.url, buildReviewExportFilename(round.original_filename))
    },
    onSuccess: () => message.success('AI批注版已开始下载'),
    onError: (error) => message.error(formatApiErrorMessage(error, 'AI批注版下载失败')),
  })

  const downloadSourceDocumentMut = useMutation({
    mutationFn: async () => {
      const { data } = await api.get<ReviewSourceDownload>(
        `/expert/review-rounds/${id}/source-download`,
      )
      await downloadFromUrl(data.url, data.filename || `任务${id}_原始方案.docx`)
      return data
    },
    onSuccess: (data) => message.success(`原始方案已开始下载；SHA-256：${data.sha256}`),
    onError: (error) => message.error(formatApiErrorMessage(error, '原始方案下载失败')),
  })

  const downloadSignedReport = async () => {
    try {
      const { data } = await api.get<SignedReportDownload>(
        `/expert/review-rounds/${id}/signed-report`,
      )
      await downloadFromUrl(
        data.url,
        `任务${detailQuery.data?.task_id ?? id}_正式签发报告.docx`,
      )
      message.success(`已开始下载；SHA-256：${data.sha256}`)
    } catch (error) {
      message.error(formatApiErrorMessage(error, '签发报告下载失败'))
    }
  }

  const openIssueEditor = (issue: ExpertReviewIssue, disposition = issue.disposition) => {
    setIssueEditing(issue)
    issueForm.setFieldsValue({
      disposition: disposition as IssueDisposition,
      final_severity: (issue.final_severity || issue.severity) as IssueDecisionForm['final_severity'],
      reviewer_comment: issue.reviewer_comment || '',
    })
  }

  const openRoundAction = (mode: RoundActionMode) => {
    const defaultConclusion: ExpertReviewConclusion =
      mode === 'approve' ? 'passed' : 'changes_required'
    roundActionForm.setFieldsValue({ conclusion: defaultConclusion, comment: '' })
    setRoundAction(mode)
  }

  if (!Number.isFinite(id) || id <= 0) {
    return <Alert type="error" showIcon message="无效的复核任务ID" />
  }

  if (detailQuery.isLoading) {
    return <div style={{ minHeight: 360, display: 'grid', placeItems: 'center' }}><Spin size="large" /></div>
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="无法打开专家复核任务"
        description={formatApiErrorMessage(
          detailQuery.error,
          '任务不存在、已删除，或当前账号没有专家复核权限。',
        )}
        action={
          <Space>
            <Button size="small" onClick={() => nav('/expert-reviews')}>返回任务池</Button>
            <Button size="small" type="primary" onClick={() => void detailQuery.refetch()}>重试</Button>
          </Space>
        }
      />
    )
  }

  const round = detailQuery.data
  const statusView = roundStatusMeta(round.status)
  const assignedToMe = round.assigned_expert_id === user?.id
  const canEdit = round.status === 'in_review' && (isManager || assignedToMe)
  const canRelease = round.status === 'in_review' && (isManager || assignedToMe)
  const canClaim =
    (round.status === 'pending' || round.status === 'in_review') &&
    (!round.assigned_expert_id || assignedToMe || !claimIsActive(round))
  const canAccessDocuments = isManager || assignedToMe
  const evidenceMissing = round.issues.filter((issue) => !issue.evidence?.trim()).length
  const evidenceUnverified = round.issues.filter((issue) => !issueEvidenceIsVerified(issue)).length
  const locationMissing = round.issues.filter((issue) => !hasIssueLocation(issue.anchor)).length
  const decisions = [...round.decisions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )
  const auditEvents = auditQuery.data ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card size="small">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <Space align="start">
            <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/expert-reviews')}>返回任务池</Button>
            <div>
              <Typography.Title level={4} style={{ margin: 0 }}>
                专家复核任务 #{round.id}
              </Typography.Title>
              <Typography.Text type="secondary">
                AI任务 #{round.task_id} · 第 {round.round_no} 轮 · {round.original_filename}
              </Typography.Text>
              <div style={{ marginTop: 8 }}>
                <Space wrap>
                  <Tag color={statusView.color}>{statusView.label}</Tag>
                  <Tag>AI结论：{REVIEW_CONCLUSION_LABELS[round.review_conclusion] ?? round.review_conclusion}</Tag>
                  <Tag color={round.completeness_status === 'complete' ? 'success' : 'warning'}>
                    完整性：{COMPLETENESS_LABELS[round.completeness_status] ?? round.completeness_status}
                  </Tag>
                  <Tag color={round.pending_issue_count > 0 ? 'error' : 'success'}>
                    待处置 {round.pending_issue_count}/{round.issue_count}
                  </Tag>
                </Space>
              </div>
            </div>
          </Space>
          <Space wrap>
            {canClaim && (!round.assigned_expert_id || !claimIsActive(round)) ? (
              <Button type="primary" icon={<LockOutlined />} loading={claimMut.isPending} onClick={() => claimMut.mutate()}>
                {round.assigned_expert_id ? '重新领取过期任务' : '领取任务'}
              </Button>
            ) : null}
            {canRelease ? (
              <Button icon={<UnlockOutlined />} onClick={() => setReleaseOpen(true)}>释放任务</Button>
            ) : null}
            <Tooltip title={!canEdit ? '请先领取任务并进入复核中状态' : undefined}>
              <Button
                danger
                icon={<RollbackOutlined />}
                disabled={!canEdit}
                onClick={() => openRoundAction('request_changes')}
              >
                退回整改
              </Button>
            </Tooltip>
            <Tooltip title={!canEdit ? '请先领取任务并完成全部问题处置' : round.pending_issue_count ? '仍有未处置问题' : undefined}>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                disabled={!canEdit || round.pending_issue_count > 0}
                onClick={() => openRoundAction('approve')}
              >
                批准
              </Button>
            </Tooltip>
            {isManager && round.status === 'approved' ? (
              <Popconfirm
                title="签发正式复核报告？"
                description="签发后报告不可覆盖，请确认全部复核记录准确。"
                okText="确认签发"
                cancelText="取消"
                onConfirm={() => signMut.mutate()}
              >
                <Button icon={<FileProtectOutlined />} loading={signMut.isPending}>签发</Button>
              </Popconfirm>
            ) : null}
            {round.signed_report_available ? (
              <Button type="primary" icon={<DownloadOutlined />} onClick={() => void downloadSignedReport()}>
                下载签发报告
              </Button>
            ) : null}
          </Space>
        </div>
      </Card>

      {round.completeness_status !== 'complete' ? (
        <Alert
          type={round.completeness_status === 'unavailable' ? 'error' : 'warning'}
          showIcon
          message="AI审查结果不完整"
          description="本任务可能存在未执行步骤或外部服务降级。专家必须结合原方案和法规独立判断，不能直接沿用AI结论。"
        />
      ) : null}
      {evidenceUnverified || locationMissing ? (
        <Alert
          type="warning"
          showIcon
          message="部分问题缺少可核验证据"
          description={`法规来源未核验 ${evidenceUnverified} 项（其中无证据文本 ${evidenceMissing} 项），缺少章节/段落定位 ${locationMissing} 项。此类问题只能作为疑似线索，必须人工核对原方案和现行法规后再处置。`}
        />
      ) : null}
      {round.assigned_expert_id && !assignedToMe && !isManager ? (
        <Alert
          type="info"
          showIcon
          message={`该任务由 ${round.assigned_expert_username || '其他专家'} 领取，当前为只读状态。`}
        />
      ) : null}

      <Card title="原文核对材料" size="small">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            专家结论必须同时核对原始方案和AI批注版。AI批注版可在线只读查看，也可下载后留档。
          </Typography.Text>
          <Space wrap>
            <Tooltip title={!canAccessDocuments ? '专家需先领取该任务；复核管理员可直接查看' : undefined}>
              <Button
                type="primary"
                icon={<EyeOutlined />}
                disabled={!canAccessDocuments}
                onClick={() => nav(`/review/${round.task_id}/preview`, {
                  state: { backTarget: `/expert-reviews/${round.id}` },
                })}
              >
                打开AI批注版（OnlyOffice）
              </Button>
            </Tooltip>
            <Tooltip title={!canAccessDocuments ? '专家需先领取该任务；复核管理员可直接下载' : undefined}>
              <Button
                icon={<DownloadOutlined />}
                disabled={!canAccessDocuments}
                loading={downloadAiDocumentMut.isPending}
                onClick={() => downloadAiDocumentMut.mutate()}
              >
                下载AI批注版
              </Button>
            </Tooltip>
            <Tooltip title={!canAccessDocuments ? '专家需先领取该任务；复核管理员可直接下载' : undefined}>
              <Button
                icon={<DownloadOutlined />}
                disabled={!canAccessDocuments}
                loading={downloadSourceDocumentMut.isPending}
                onClick={() => downloadSourceDocumentMut.mutate()}
              >
                下载原始方案
              </Button>
            </Tooltip>
          </Space>
          {!canAccessDocuments ? (
            <Alert
              type="info"
              showIcon
              message="当前只能查看复核摘要"
              description="领取任务后即可访问原始方案和AI批注版，避免未授权下载工程文件。"
            />
          ) : null}
        </Space>
      </Card>

      <Card title="任务信息" size="small">
        <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
          <Descriptions.Item label="方案类型">{round.scheme_category} / {round.scheme_name}</Descriptions.Item>
          <Descriptions.Item label="项目名称">{round.project_name?.trim() || '历史任务未关联项目'}</Descriptions.Item>
          <Descriptions.Item label="项目所在地">{round.project_region?.trim() || '未填写'}</Descriptions.Item>
          <Descriptions.Item label="提交人">{round.task_owner_username || '—'}</Descriptions.Item>
          <Descriptions.Item label="关联版本">
            {round.version_label?.trim() || (round.document_revision_id ? `历史版本 #${round.document_revision_id}` : '历史任务未关联版本')}
          </Descriptions.Item>
          <Descriptions.Item label="项目ID">{round.project_id ? `#${round.project_id}` : '—'}</Descriptions.Item>
          <Descriptions.Item label="领取专家">{round.assigned_expert_username || '未领取'}</Descriptions.Item>
          <Descriptions.Item label="领取时间">{formatReviewTime(round.claimed_at)}</Descriptions.Item>
          <Descriptions.Item label="领取有效期">{formatReviewTime(round.claim_expires_at)}</Descriptions.Item>
          <Descriptions.Item label="复核结论">{round.conclusion ? REVIEW_CONCLUSION_LABELS[round.conclusion] ?? round.conclusion : '尚未形成'}</Descriptions.Item>
          <Descriptions.Item label="批准时间">{formatReviewTime(round.approved_at)}</Descriptions.Item>
          <Descriptions.Item label="签发时间">{formatReviewTime(round.signed_at)}</Descriptions.Item>
          <Descriptions.Item label="最终意见" span={3}>{round.final_comment || '—'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="逐项问题复核" size="small">
        {round.issues.length === 0 ? (
          <Empty description="AI报告中没有可供逐项复核的问题；仍需人工确认报告完整性与方案原文。" />
        ) : (
          <Table<ExpertReviewIssue>
            rowKey="id"
            dataSource={round.issues}
            pagination={{ defaultPageSize: 20, showSizeChanger: true }}
            scroll={{ x: 1350 }}
            expandable={{
              expandedRowRender: (issue) => {
                const suggestions = extractSuggestions(issue.related)
                return (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {suggestions.length ? (
                      <div>
                        <Typography.Text strong>AI整改建议：</Typography.Text>
                        <ul style={{ marginBottom: 0 }}>{suggestions.map((item, index) => <li key={index}>{item}</li>)}</ul>
                      </div>
                    ) : null}
                    <Collapse
                      ghost
                      items={[
                        { key: 'anchor', label: '原始定位数据', children: <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(issue.anchor, null, 2)}</pre> },
                        { key: 'related', label: '审查依据与状态', children: <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(translateReviewMetadata(issue.related), null, 2)}</pre> },
                      ]}
                    />
                  </Space>
                )
              },
            }}
            columns={[
              {
                title: '来源/等级',
                key: 'source',
                width: 130,
                render: (_, issue) => {
                  const severity = SEVERITY_META[issue.final_severity || issue.severity] ?? { label: issue.final_severity || issue.severity, color: 'default' }
                  return <Space direction="vertical" size={4}><Tag>{STEP_LABELS[issue.step_id] ?? issue.step_id}</Tag><Tag color={severity.color}>{severity.label}</Tag></Space>
                },
              },
              {
                title: 'AI问题',
                dataIndex: 'message',
                width: 300,
                render: (value: string) => <Typography.Text>{value || '—'}</Typography.Text>,
              },
              {
                title: '证据与定位',
                key: 'evidence',
                width: 360,
                render: (_, issue) => (
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    {issue.evidence?.trim() ? <Typography.Text type="secondary">{issue.evidence}</Typography.Text> : <Tag color="warning">缺少原文证据</Tag>}
                    {issueEvidenceIsVerified(issue) ? (
                      <Tag color="success">法规证据已核验</Tag>
                    ) : (
                      <Tag color="warning">疑似问题，待人工核验法规来源</Tag>
                    )}
                    {issue.related.formal_violation === true ? <Tag color="error">已标记形式违规</Tag> : null}
                    {issue.related.requires_human_judgement === true ? <Tag color="processing">需要人工专业判断</Tag> : null}
                    {hasIssueLocation(issue.anchor) ? <Typography.Text type="secondary">定位：{issueLocationText(issue.anchor)}</Typography.Text> : <Tag color="warning">未定位到原文章节或段落</Tag>}
                  </Space>
                ),
              },
              {
                title: '专家处置',
                key: 'decision',
                width: 260,
                render: (_, issue) => {
                  const meta = DISPOSITION_META[issue.disposition] ?? { label: issue.disposition, color: 'default' }
                  return (
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <Tag color={meta.color}>{meta.label}</Tag>
                      {issue.reviewer_comment ? <Typography.Text type="secondary">{issue.reviewer_comment}</Typography.Text> : <Typography.Text type="secondary">暂无专家备注</Typography.Text>}
                      {issue.reviewed_at ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>处置时间：{formatReviewTime(issue.reviewed_at)}</Typography.Text> : null}
                    </Space>
                  )
                },
              },
              {
                title: '操作',
                key: 'actions',
                width: 250,
                fixed: 'right',
                render: (_, issue) => (
                  <Space wrap size="small">
                    <Tooltip title={!canEdit ? '当前任务不可编辑或尚未领取' : undefined}>
                      <Button size="small" icon={<CheckOutlined />} disabled={!canEdit} onClick={() => openIssueEditor(issue, 'accepted')}>接受</Button>
                    </Tooltip>
                    <Tooltip title={!canEdit ? '当前任务不可编辑或尚未领取' : undefined}>
                      <Button size="small" icon={<CloseOutlined />} disabled={!canEdit} onClick={() => openIssueEditor(issue, 'rejected')}>驳回</Button>
                    </Tooltip>
                    <Tooltip title={!canEdit ? '当前任务不可编辑或尚未领取' : undefined}>
                      <Button size="small" icon={<EditOutlined />} disabled={!canEdit} onClick={() => openIssueEditor(issue)}>改等级/备注</Button>
                    </Tooltip>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Card title="复核与审计时间线" size="small">
        {decisions.length === 0 ? (
          <Empty description="暂无复核操作记录" />
        ) : (
          <Timeline
            items={decisions.map((decision) => ({
              color: decision.action === 'signed' || decision.action === 'approve' ? 'green' : decision.action === 'request_changes' ? 'red' : 'blue',
              children: (
                <div>
                  <Typography.Text strong>{DECISION_ACTION_LABELS[decision.action] ?? decision.action}</Typography.Text>
                  <Typography.Text type="secondary"> · {formatReviewTime(decision.created_at)} · 操作人ID {decision.actor_id ?? '系统'}</Typography.Text>
                  {decision.from_status || decision.to_status ? <div><Tag>{decision.from_status || '—'}</Tag> → <Tag>{decision.to_status || '—'}</Tag></div> : null}
                  {decision.comment ? <Typography.Paragraph style={{ margin: '4px 0 0' }}>{decision.comment}</Typography.Paragraph> : null}
                </div>
              ),
            }))}
          />
        )}
        {isManager ? (
          <Collapse
            items={[
              {
                key: 'audit-events',
                label: `底层审计事件（${auditEvents.length}）`,
                children: auditQuery.isError ? (
                  <Alert type="error" showIcon message={formatApiErrorMessage(auditQuery.error, '审计事件加载失败')} />
                ) : (
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {JSON.stringify(auditEvents, null, 2)}
                  </pre>
                ),
              },
            ]}
          />
        ) : null}
      </Card>

      <Modal
        title={issueEditing ? `问题处置 #${issueEditing.id}` : '问题处置'}
        open={issueEditing !== null}
        onCancel={() => { setIssueEditing(null); issueForm.resetFields() }}
        okText="保存处置"
        confirmLoading={issueMut.isPending}
        onOk={() => issueForm.submit()}
        destroyOnClose
      >
        {issueEditing ? (
          <>
            <Alert
              type={issueEvidenceIsVerified(issueEditing) && hasIssueLocation(issueEditing.anchor) ? 'info' : 'warning'}
              showIcon
              style={{ marginBottom: 16 }}
              message={issueEditing.message}
              description={
                issueEvidenceIsVerified(issueEditing)
                  ? issueEditing.evidence?.trim() || '法规证据已核验，但未提供证据摘要。'
                  : `疑似问题，待人工核验法规来源。${issueEditing.evidence?.trim() ? ` AI提供的待核验线索：${issueEditing.evidence.trim()}` : ' AI未提供证据文本。'}`
              }
            />
            <Form<IssueDecisionForm>
              form={issueForm}
              layout="vertical"
              onFinish={(values) => {
                if (values.disposition === 'modified' && !values.final_severity) {
                  message.warning('修改问题等级时必须选择最终等级')
                  return
                }
                issueMut.mutate({ issueId: issueEditing.id, values })
              }}
            >
              <Form.Item name="disposition" label="处置结论" rules={[{ required: true, message: '请选择处置结论' }]}>
                <Select options={[
                  { value: 'accepted', label: '接受：确认AI问题成立' },
                  { value: 'rejected', label: '驳回：确认为AI误报' },
                  { value: 'modified', label: '修改：调整问题等级' },
                  { value: 'resolved', label: '已整改：确认当前版本已解决' },
                  { value: 'pending', label: '暂缓：保持待处置' },
                ]} />
              </Form.Item>
              <Form.Item name="final_severity" label="最终问题等级">
                <Select allowClear options={[
                  { value: 'error', label: '严重' },
                  { value: 'warning', label: '警告' },
                  { value: 'info', label: '提示' },
                ]} />
              </Form.Item>
              <Form.Item name="reviewer_comment" label="专家备注" rules={[{ max: 4000, message: '最多4000字' }]}>
                <Input.TextArea rows={5} placeholder="记录判断依据、法规条款或需要补充核验的内容" />
              </Form.Item>
            </Form>
          </>
        ) : null}
      </Modal>

      <Modal
        title="释放复核任务"
        open={releaseOpen}
        onCancel={() => setReleaseOpen(false)}
        okText="确认释放"
        confirmLoading={releaseMut.isPending}
        onOk={() => releaseMut.mutate(releaseComment)}
      >
        <Typography.Paragraph type="secondary">释放后其他专家可以重新领取。</Typography.Paragraph>
        <Input.TextArea rows={4} value={releaseComment} onChange={(event) => setReleaseComment(event.target.value)} placeholder="可填写释放原因" maxLength={8000} showCount />
      </Modal>

      <Modal
        title={roundAction === 'approve' ? '批准专家复核' : '退回整改'}
        open={roundAction !== null}
        onCancel={() => { setRoundAction(null); roundActionForm.resetFields() }}
        okText={roundAction === 'approve' ? '确认批准' : '确认退回'}
        okButtonProps={{ danger: roundAction === 'request_changes' }}
        confirmLoading={roundActionMut.isPending}
        onOk={() => roundActionForm.submit()}
      >
        <Form<RoundActionForm>
          form={roundActionForm}
          layout="vertical"
          onFinish={(values) => roundAction && roundActionMut.mutate({ mode: roundAction, values })}
        >
          <Form.Item name="conclusion" label="复核结论" rules={[{ required: true }]}>
            <Select options={
              roundAction === 'approve'
                ? [
                    { value: 'passed', label: '通过' },
                    { value: 'conditional_pass', label: '有条件通过' },
                  ]
                : [
                    { value: 'changes_required', label: '需要整改' },
                    { value: 'rejected', label: '不通过' },
                  ]
            } />
          </Form.Item>
          <Form.Item
            name="comment"
            label={roundAction === 'approve' ? '最终复核意见' : '整改要求'}
            rules={roundAction === 'request_changes' ? [{ required: true, whitespace: true, message: '退回整改必须填写具体意见' }] : []}
          >
            <Input.TextArea rows={6} maxLength={8000} showCount placeholder="填写可执行、可追溯的专家意见" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
