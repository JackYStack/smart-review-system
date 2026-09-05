import './ReviewPage.css'

import {
  AuditOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  ExportOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  HistoryOutlined,
  ProfileOutlined,
  RedoOutlined,
  StopOutlined,
  UploadOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import {
  App as AntApp,
  Alert,
  Button,
  Col,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  api,
  getReviewArtifactDownloadUrl,
  getReviewTaskArtifacts,
} from '../api/client'
import type {
  DocumentArtifact,
  ProjectCreate,
  ProjectPublic,
  RevisionTaskCreateResponse,
  ReviewTask,
  SchemeType,
} from '../api/types'
import { useAuth } from '../auth/AuthContext'
import PageShell from '../components/PageShell'
import { DEFAULT_TABLE_PAGINATION } from '../config/tablePagination'
import {
  buildAuditReportFilename,
  buildReviewExportFilename,
} from '../utils/reviewExportFilename'
import { formatApiErrorMessage } from '../utils/apiError'

const statusLabel: Record<string, string> = {
  pending: '排队中',
  processing: '处理中',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
}

const REVIEW_STAGE_LABELS: Record<string, string> = {
  structure: '结构审核',
  compilation_basis: '编制依据审核',
  context_consistency: '上下文一致性',
  content: '内容审核',
  full_document: '通篇审核',
  dify_workflow: 'Dify Workflow 全文审查',
}

const tagSx = { border: 'none', marginInlineEnd: 0 } as const

function pillTag(text: string, background: string, color: string) {
  return (
    <Tag style={{ ...tagSx, background, color }}>
      {text}
    </Tag>
  )
}

function statusTag(status: string) {
  if (status === 'succeeded') {
    return pillTag(statusLabel[status] ?? status, '#f6ffed', '#237804')
  }
  if (status === 'failed') {
    return pillTag(statusLabel[status] ?? status, '#fff2f0', '#a8071a')
  }
  if (status === 'canceled') {
    return pillTag(statusLabel[status] ?? status, '#f5f5f5', '#595959')
  }
  return pillTag(statusLabel[status] ?? status, '#e6f4ff', '#0958d9')
}

function taskStatusCell(row: ReviewTask) {
  let tag: ReactNode
  if (row.status === 'processing' && row.cancel_requested_at) {
    tag = pillTag('取消请求已提交', '#fff7e6', '#ad4e00')
  } else if (row.status === 'processing' && row.review_stage) {
    const label = REVIEW_STAGE_LABELS[row.review_stage] ?? row.review_stage
    if (
      row.review_stage === 'content' ||
      row.review_stage === 'full_document' ||
      row.review_stage === 'dify_workflow'
    ) {
      tag = pillTag(label, '#fff7e6', '#d46b08')
    } else {
      tag = pillTag(label, '#e6f4ff', '#0958d9')
    }
  } else {
    tag = statusTag(row.status)
  }
  return row.error_message?.trim() ? <Tooltip title={row.error_message}>{tag}</Tooltip> : tag
}

function generateIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `submit-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

function formatDurationMinutes(durationMs?: number | null): string {
  if (typeof durationMs !== 'number' || !Number.isFinite(durationMs) || durationMs < 0) {
    return '—'
  }
  return (durationMs / 60000).toFixed(1)
}

function formatTokenCount(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    return '—'
  }
  return String(value)
}

function tokensCell(row: ReviewTask, isAdmin: boolean) {
  if (isAdmin) {
    return (
      <div className="review-page__tokens-split">
        <span>
          输入 <span className="review-page__tokens-num">{formatTokenCount(row.input_tokens)}</span>
        </span>
        <span>
          输出 <span className="review-page__tokens-num">{formatTokenCount(row.output_tokens)}</span>
        </span>
      </div>
    )
  }
  return formatTokenCount(row.total_tokens)
}

function normalizedStatus(value?: string | null): string {
  return String(value ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function schemeIsReady(scheme: SchemeType): boolean {
  if (scheme.lifecycle_status !== 'published') return false
  const status = normalizedStatus(scheme.readiness_status)
  if (!status) return scheme.template_configured && scheme.workflow_configured
  return ['ready', 'configured', 'available', '已就绪', '可用'].includes(status)
}

function schemeAvailabilityIssues(scheme: SchemeType): string[] {
  const issues: string[] = []
  if (scheme.lifecycle_status !== 'published') {
    issues.push(`${scheme.category} / ${scheme.name}：尚未发布`)
  }
  if (scheme.readiness_issues?.length) {
    issues.push(...scheme.readiness_issues.map((item) => `${scheme.category} / ${scheme.name}：${item}`))
  } else if (scheme.lifecycle_status === 'published' && !schemeIsReady(scheme)) {
    issues.push(`${scheme.category} / ${scheme.name}：审核配置尚未就绪`)
  }
  return issues
}

function reviewConclusionTag(value?: string | null) {
  const status = normalizedStatus(value)
  if (['passed', 'compliant', 'no_issues', '通过', '合规'].includes(status)) {
    return pillTag('审查通过', '#f6ffed', '#237804')
  }
  if (['conditional_pass', '有条件通过'].includes(status)) {
    return pillTag('有条件通过', '#fff7e6', '#ad4e00')
  }
  if (
    ['issues_found', 'changes_required', 'non_compliant', 'noncompliant', 'failed', '发现问题', '需整改', '不合规'].includes(
      status,
    )
  ) {
    return pillTag(status === 'changes_required' || status === '需整改' ? '需整改' : '发现问题', '#fff2f0', '#a8071a')
  }
  if (['rejected', 'not_passed', '不通过'].includes(status)) {
    return pillTag('不通过', '#fff1f0', '#820014')
  }
  if (['unable_to_determine', 'undetermined', '无法判断'].includes(status)) {
    return pillTag('无法判断', '#f9f0ff', '#531dab')
  }
  if (['not_reviewed', 'unavailable', '未审查', '未形成结论'].includes(status)) {
    return pillTag('未形成结论', '#f5f5f5', '#595959')
  }
  return pillTag(value?.trim() || '未记录', '#f5f5f5', '#595959')
}

function completenessTag(value?: string | null) {
  const status = normalizedStatus(value)
  if (['complete', 'full', '完整'].includes(status)) {
    return pillTag('结果完整', '#f6ffed', '#237804')
  }
  if (['partial', 'degraded', 'incomplete', '部分', '降级'].includes(status)) {
    return pillTag('降级/部分结果', '#fff7e6', '#ad4e00')
  }
  if (['unavailable', 'none', 'missing', '不可用', '无结果'].includes(status)) {
    return pillTag('结果不可用', '#fff2f0', '#a8071a')
  }
  return pillTag(value?.trim() || '未记录', '#f5f5f5', '#595959')
}

function humanStatusTag(value?: string | null) {
  const status = normalizedStatus(value)
  if (['pending', 'awaiting_review', 'not_started', '待复核', '待人工复核'].includes(status)) {
    return pillTag('待人工复核', '#e6f4ff', '#0958d9')
  }
  if (['in_review', 'reviewing', '复核中'].includes(status)) {
    return pillTag('人工复核中', '#fff7e6', '#ad4e00')
  }
  if (['approved', 'confirmed', 'completed', '已确认', '已通过'].includes(status)) {
    return pillTag('人工已确认', '#f6ffed', '#237804')
  }
  if (['changes_requested', 'rejected', '待整改', '退回整改'].includes(status)) {
    return pillTag('待整改', '#fff2f0', '#a8071a')
  }
  if (['not_required', '无需复核'].includes(status)) {
    return pillTag('无需复核', '#f5f5f5', '#595959')
  }
  return pillTag(value?.trim() || '未记录', '#f5f5f5', '#595959')
}

function reportMayExist(row: ReviewTask): boolean {
  const status = normalizedStatus(row.completeness_status)
  if (['unavailable', 'none', 'missing', '不可用', '无结果'].includes(status)) return false
  return row.status === 'succeeded' || row.status === 'failed'
}

const ARTIFACT_KIND_VIEW: Record<string, { label: string; color: string }> = {
  original: { label: '原始方案', color: 'default' },
  ai_annotated: { label: 'AI 批注版', color: 'processing' },
  expert_edit: { label: '专家编辑版', color: 'warning' },
  signed_report: { label: '正式签发报告', color: 'success' },
}

const ARTIFACT_KIND_ORDER = ['original', 'ai_annotated', 'expert_edit', 'signed_report'] as const

function artifactKindView(kind: string): { label: string; color: string } {
  return ARTIFACT_KIND_VIEW[kind] ?? { label: kind || '其他文档', color: 'default' }
}

function formatArtifactSize(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes < 0) return '—'
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatArtifactTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', { hour12: false })
}

function groupDocumentArtifacts(artifacts: DocumentArtifact[]) {
  const extraKinds = Array.from(
    new Set(
      artifacts
        .map((item) => item.artifact_kind)
        .filter((kind) => !ARTIFACT_KIND_ORDER.includes(kind as (typeof ARTIFACT_KIND_ORDER)[number])),
    ),
  )
  return [...ARTIFACT_KIND_ORDER, ...extraKinds].map((kind) => ({
    kind,
    view: artifactKindView(kind),
    items: artifacts
      .filter((item) => item.artifact_kind === kind)
      .sort((left, right) => right.version_no - left.version_no),
  }))
}

async function downloadWordV2(taskId: number, downloadName: string): Promise<void> {
  const { data } = await api.get<{ url: string }>(
    `/review-tasks/${taskId}/output-download-url`,
  )
  const res = await fetch(data.url)
  if (!res.ok) throw new Error('下载失败')
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = downloadName
  a.rel = 'noopener'
  a.click()
  URL.revokeObjectURL(a.href)
}

async function downloadAuditReport(taskId: number, downloadName: string): Promise<void> {
  const { data } = await api.get<Blob>(`/review-tasks/${taskId}/audit-report`, {
    responseType: 'blob',
  })
  const blob = data instanceof Blob ? data : new Blob([data])
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = downloadName
  a.rel = 'noopener'
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function ReviewPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { message } = AntApp.useApp()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [schemeId, setSchemeId] = useState<number | null>(null)
  const [submitOpen, setSubmitOpen] = useState(false)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [supportingFileList, setSupportingFileList] = useState<UploadFile[]>([])
  const [siteImageFileList, setSiteImageFileList] = useState<UploadFile[]>([])
  const [projectId, setProjectId] = useState<number | null>(null)
  const [versionLabel, setVersionLabel] = useState('V1')
  const [newProjectOpen, setNewProjectOpen] = useState(false)
  const [reviewFocus, setReviewFocus] = useState('')
  const [priority, setPriority] = useState(0)
  const [submitIdempotencyKey, setSubmitIdempotencyKey] = useState('')
  const [projectForm] = Form.useForm<ProjectCreate>()
  const [logModalTaskId, setLogModalTaskId] = useState<number | null>(null)
  const [logLoading, setLogLoading] = useState(false)
  const [logContent, setLogContent] = useState<string | null>(null)
  const [artifactTask, setArtifactTask] = useState<ReviewTask | null>(null)
  const [downloadingArtifactId, setDownloadingArtifactId] = useState<number | null>(null)

  const {
    data: schemes = [],
    isLoading: schemesLoading,
    isError: schemesIsError,
    error: schemesError,
    refetch: refetchSchemes,
  } = useQuery({
    queryKey: ['schemes'],
    queryFn: async () => {
      const { data: rows } = await api.get<SchemeType[]>('/scheme-types')
      return rows
    },
  })

  const withTemplate = useMemo(
    () => schemes.filter((s) => s.template_configured),
    [schemes],
  )

  const readySchemes = useMemo(() => withTemplate.filter(schemeIsReady), [withTemplate])

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const { data } = await api.get<ProjectPublic[]>('/projects')
      return data
    },
  })

  useEffect(() => {
    const projects = projectsQuery.data ?? []
    if (!projects.length) {
      setProjectId(null)
      return
    }
    if (projectId == null || !projects.some((project) => project.id === projectId)) {
      setProjectId(projects[0].id)
    }
  }, [projectId, projectsQuery.data])

  const {
    data: tasks = [],
    isLoading: tasksLoading,
    isError: tasksIsError,
    error: tasksError,
    refetch: refetchTasks,
  } = useQuery({
    queryKey: ['review-tasks'],
    queryFn: async () => {
      const { data } = await api.get<ReviewTask[]>('/review-tasks')
      return data
    },
    refetchInterval: (query) => {
      const rows = query.state.data
      if (!rows?.length) return 4000
      const active = rows.some(
        (r) => r.status === 'pending' || r.status === 'processing',
      )
      return active ? 3000 : false
    },
  })

  const artifactTaskId = artifactTask?.id
  const artifactsQuery = useQuery({
    queryKey: ['review-task-artifacts', artifactTaskId],
    enabled: artifactTaskId != null,
    queryFn: () => getReviewTaskArtifacts(artifactTaskId as number),
    staleTime: 15_000,
  })
  const artifactGroups = useMemo(
    () => groupDocumentArtifacts(artifactsQuery.data ?? []),
    [artifactsQuery.data],
  )

  const reviewStats = useMemo(() => {
    const total = tasks.length
    const pendingManual = tasks.filter((t) => {
      const status = normalizedStatus(t.human_status)
      if (!status) return t.status === 'succeeded'
      return ['pending', 'awaiting_review', 'not_started', '待复核', '待人工复核'].includes(status)
    }).length
    const anomaly = tasks.filter((t) => t.status === 'failed').length
    return { total, pendingManual, anomaly }
  }, [tasks])

  const createProjectMut = useMutation({
    mutationFn: async (values: ProjectCreate) => {
      const { data } = await api.post<ProjectPublic>('/projects', {
        name: values.name.trim(),
        region: values.region?.trim() || '',
        construction_unit: values.construction_unit?.trim() || '',
        contractor: values.contractor?.trim() || '',
        supervision_unit: values.supervision_unit?.trim() || '',
      })
      return data
    },
    onSuccess: async (project) => {
      message.success('项目已创建并选中')
      qc.setQueryData<ProjectPublic[]>(['projects'], (current = []) => [
        project,
        ...current.filter((item) => item.id !== project.id),
      ])
      setProjectId(project.id)
      setNewProjectOpen(false)
      projectForm.resetFields()
      await qc.invalidateQueries({ queryKey: ['projects'] })
    },
    onError: (err: unknown) => message.error(formatApiErrorMessage(err, '创建项目失败')),
  })

  const submitMut = useMutation({
    mutationFn: async ({
      sid,
      file,
      supportingFiles,
      siteImages,
      requestKey,
      targetProjectId,
      targetVersionLabel,
    }: {
      sid: number
      file: File
      supportingFiles: File[]
      siteImages: File[]
      requestKey: string
      targetProjectId: number
      targetVersionLabel: string
    }) => {
      const fd = new FormData()
      fd.append('scheme_type_id', String(sid))
      fd.append('version_label', targetVersionLabel.trim())
      fd.append('review_focus', reviewFocus.trim())
      fd.append('idempotency_key', requestKey)
      if (isAdmin) fd.append('priority', String(priority))
      fd.append('file', file)
      supportingFiles.forEach((item) => fd.append('attachments', item))
      siteImages.forEach((item) => fd.append('site_images', item))
      const { data } = await api.post<RevisionTaskCreateResponse>(
        `/projects/${targetProjectId}/revisions`,
        fd,
      )
      return data
    },
    onSuccess: async (data) => {
      message.success(`项目版本 ${data.revision.version_label} 已提交，审核任务 #${data.task_id}`)
      setSubmitOpen(false)
      setFileList([])
      setSupportingFileList([])
      setSiteImageFileList([])
      setSubmitIdempotencyKey('')
      await qc.invalidateQueries({ queryKey: ['review-tasks'] })
    },
    onError: (err: unknown) => message.error(formatApiErrorMessage(err, '提交失败')),
  })

  const cancelMut = useMutation({
    mutationFn: async (taskId: number) => {
      const { data } = await api.post<ReviewTask>(`/review-tasks/${taskId}/cancel`)
      return data
    },
    onSuccess: async (task) => {
      if (task.status === 'processing') {
        message.info('取消请求已提交；系统将在当前安全检查点停止任务')
      } else {
        message.success('任务已取消')
      }
      await qc.invalidateQueries({ queryKey: ['review-tasks'] })
    },
    onError: (err: unknown) => message.error(formatApiErrorMessage(err, '取消任务失败')),
  })

  const retryMut = useMutation({
    mutationFn: async (taskId: number) => {
      const { data } = await api.post<{ task: ReviewTask; message?: string }>(
        `/review-tasks/${taskId}/retry`,
      )
      return data
    },
    onSuccess: async (data) => {
      message.success(data.message || `已创建重试任务 #${data.task.id}`)
      await qc.invalidateQueries({ queryKey: ['review-tasks'] })
    },
    onError: (err: unknown) => message.error(formatApiErrorMessage(err, '重试任务失败')),
  })

  const deleteMut = useMutation({
    mutationFn: async (taskId: number) => {
      await api.delete(`/review-tasks/${taskId}`)
    },
    onSuccess: async () => {
      message.success('已删除该审核任务')
      await qc.invalidateQueries({ queryKey: ['review-tasks'] })
    },
    onError: (err: unknown) => {
      const detailMsg =
        err &&
        typeof err === 'object' &&
        'response' in err &&
        err.response &&
        typeof err.response === 'object' &&
        'data' in err.response &&
        err.response.data &&
        typeof err.response.data === 'object' &&
        'detail' in err.response.data
          ? String((err.response.data as { detail?: unknown }).detail)
          : ''
      message.error(detailMsg || '删除失败')
    },
  })

  const handleDownloadTemplate = async () => {
    if (!schemeId) {
      message.warning('请先选择方案类型')
      return
    }
    try {
      const { data } = await api.get<{ url: string }>(
        `/scheme-types/${schemeId}/template/download-url`,
      )
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch {
      message.warning('无法获取模版下载链接（该类型可能尚未上传模版）')
    }
  }

  const openSubmit = () => {
    if (!schemeId) {
      message.warning('请先选择方案类型')
      return
    }
    const selected = schemes.find((item) => item.id === schemeId)
    if (!selected || !schemeIsReady(selected)) {
      message.warning(selected ? schemeAvailabilityIssues(selected).join('；') : '该方案类型不可用')
      return
    }
    setFileList([])
    setSupportingFileList([])
    setSiteImageFileList([])
    setVersionLabel('V1')
    setReviewFocus('')
    setPriority(0)
    setSubmitIdempotencyKey(generateIdempotencyKey())
    setSubmitOpen(true)
  }

  const confirmSubmit = () => {
    if (!schemeId) return
    if (!projectId) {
      message.warning('请先选择或新建项目')
      return
    }
    if (!versionLabel.trim()) {
      message.warning('请填写本次方案版本号')
      return
    }
    const selected = schemes.find((item) => item.id === schemeId)
    if (!selected || !schemeIsReady(selected)) {
      message.warning(selected ? schemeAvailabilityIssues(selected).join('；') : '该方案类型不可用')
      return
    }
    const f = fileList[0]?.originFileObj
    if (!f) {
      message.warning('请选择要上传的 .docx 文件')
      return
    }
    const supportingFiles = supportingFileList
      .map((item) => item.originFileObj)
      .filter((item): item is NonNullable<typeof item> => Boolean(item))
    const siteImages = siteImageFileList
      .map((item) => item.originFileObj)
      .filter((item): item is NonNullable<typeof item> => Boolean(item))
    const requestKey = submitIdempotencyKey || generateIdempotencyKey()
    if (!submitIdempotencyKey) setSubmitIdempotencyKey(requestKey)
    submitMut.mutate({
      sid: schemeId,
      file: f,
      supportingFiles,
      siteImages,
      requestKey,
      targetProjectId: projectId,
      targetVersionLabel: versionLabel,
    })
  }

  const openReviewLog = async (taskId: number) => {
    setLogModalTaskId(taskId)
    setLogLoading(true)
    setLogContent(null)
    try {
      const { data } = await api.get<ReviewTask>(`/review-tasks/${taskId}`)
      const text = data.review_log?.trim()
      setLogContent(text && text.length > 0 ? text : '暂无审核日志')
    } catch {
      message.error('加载审核日志失败')
      setLogContent(null)
    } finally {
      setLogLoading(false)
    }
  }

  const handleExport = async (row: ReviewTask) => {
    if (row.status !== 'succeeded' && row.status !== 'failed') {
      message.warning('任务尚未完成，暂无法导出方案')
      return
    }
    if (!row.output_object_key?.trim()) {
      message.warning('该任务未生成带批注的审核方案，不能以原始文件代替审核结果')
      return
    }
    try {
      const name = buildReviewExportFilename(row.original_filename)
      await downloadWordV2(row.id, name)
      message.success(`已开始下载 ${name}`)
    } catch {
      message.error('导出失败')
    }
  }

  const handleAuditReportExport = async (row: ReviewTask) => {
    if (row.status !== 'succeeded' && row.status !== 'failed') {
      message.warning('任务尚未完成，暂无法导出审核报告')
      return
    }
    if (!reportMayExist(row)) {
      message.warning('该任务尚未形成可导出的审核报告')
      return
    }
    try {
      const name = buildAuditReportFilename(row.original_filename)
      await downloadAuditReport(row.id, name)
      message.success(`已开始下载 ${name}`)
    } catch {
      message.error('导出审核报告失败')
    }
  }

  const handleArtifactDownload = async (artifact: DocumentArtifact) => {
    if (!artifactTask) return
    setDownloadingArtifactId(artifact.id)
    try {
      const data = await getReviewArtifactDownloadUrl(artifactTask.id, artifact.id)
      if (!data.url?.trim()) throw new Error('服务未返回下载地址')
      const link = document.createElement('a')
      link.href = data.url
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      link.download = artifact.original_filename || `document-v${artifact.version_no}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      message.success(`已开始下载 ${artifact.original_filename || `文档 v${artifact.version_no}`}`)
    } catch (error) {
      message.error(formatApiErrorMessage(error, '文档版本下载失败'))
    } finally {
      setDownloadingArtifactId(null)
    }
  }

  return (
    <div className="review-page">
      <PageShell
        icon={<FileSearchOutlined />}
        description="上传 Word 后由 PaddleOCR 识别标题、正文、表格与公式，再进入结构校验和智能审查；完成后可人工审阅并导出带批注文档。"
      >
        {schemesIsError ? (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
            message="方案类型加载失败"
            description={formatApiErrorMessage(schemesError, '无法连接审核服务，请检查服务状态后重试。')}
            action={<Button size="small" onClick={() => void refetchSchemes()}>重试</Button>}
          />
        ) : null}
        {tasksIsError ? (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
            message="审核任务加载失败"
            description={formatApiErrorMessage(tasksError, '无法读取任务列表，请稍后重试。')}
            action={<Button size="small" onClick={() => void refetchTasks()}>重试</Button>}
          />
        ) : null}
        <div className="review-page__stats">
          <div className="review-page__stat-card">
            <FileSearchOutlined className="review-page__stat-icon" aria-hidden />
            <div className="review-page__stat-body">
              <div className="review-page__stat-label">总审核数</div>
              <Typography.Title level={4} className="review-page__stat-value">
                {reviewStats.total}
              </Typography.Title>
            </div>
          </div>
          <div className="review-page__stat-card">
            <AuditOutlined className="review-page__stat-icon review-page__stat-icon--audit" aria-hidden />
            <div className="review-page__stat-body">
              <div className="review-page__stat-label">待人工审核</div>
              <Typography.Title level={4} className="review-page__stat-value">
                {reviewStats.pendingManual}
              </Typography.Title>
            </div>
          </div>
          <div className="review-page__stat-card">
            <WarningOutlined className="review-page__stat-icon review-page__stat-icon--warn" aria-hidden />
            <div className="review-page__stat-body">
              <div className="review-page__stat-label">审核异常</div>
              <Typography.Title level={4} className="review-page__stat-value">
                {reviewStats.anomaly}
              </Typography.Title>
            </div>
          </div>
        </div>

        <div className="review-page__filters">
          <Space wrap size="middle">
            <Select
              placeholder="选择方案类型"
              loading={schemesLoading}
              style={{ minWidth: 260 }}
              allowClear
              value={schemeId ?? undefined}
              onChange={(v) => setSchemeId(typeof v === 'number' ? v : null)}
              options={withTemplate.map((s) => ({
                value: s.id,
                label: `${s.category} / ${s.name}${schemeIsReady(s) ? '' : s.lifecycle_status !== 'published' ? '（未发布）' : '（未就绪）'}`,
                disabled: !schemeIsReady(s),
              }))}
            />
            <Button icon={<CloudDownloadOutlined />} onClick={handleDownloadTemplate}>
              下载模版
            </Button>
            <Button type="primary" icon={<UploadOutlined />} onClick={openSubmit}>
              方案审核
            </Button>
          </Space>
        </div>

        {!schemesLoading && !schemesIsError && readySchemes.length === 0 ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 12 }}
            message="暂无可提交审核的方案类型"
            description={
              withTemplate.length === 0
                ? '尚未上传并解析方案模板，请联系管理员完成模板配置。'
                : Array.from(
                    new Set(
                      withTemplate.flatMap(schemeAvailabilityIssues),
                    ),
                  ).join('；')
            }
          />
        ) : null}

        <div className="review-page__table-wrap">
        <Table<ReviewTask>
          rowKey="id"
          size="middle"
          loading={tasksLoading}
          dataSource={tasks}
          locale={{ emptyText: '暂无审核任务' }}
          pagination={DEFAULT_TABLE_PAGINATION}
          scroll={{ x: 2370 }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 72 },
            ...(isAdmin
              ? [
                  {
                    title: '用户名',
                    key: 'owner_username',
                    width: 120,
                    ellipsis: true,
                    render: (_: unknown, row: ReviewTask) =>
                      row.owner_username?.trim() ? row.owner_username : '—',
                  },
                ]
              : []),
            {
              title: '方案类型',
              key: 'scheme',
              render: (_, row) => `${row.scheme_category} / ${row.scheme_name}`,
            },
            {
              title: '文件',
              key: 'original_filename',
              ellipsis: { showTitle: false },
              render: (_, row) => (
                <Tooltip title={row.original_filename}>
                  <Typography.Text ellipsis className="review-page__filename">
                    {row.original_filename}
                  </Typography.Text>
                </Tooltip>
              ),
            },
            {
              title: '技术状态',
              key: 'status',
              width: 130,
              render: (_, row) => taskStatusCell(row),
            },
            {
              title: '队列/尝试',
              key: 'queue_attempt',
              width: 130,
              render: (_, row) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text>第 {row.attempt_no || 1} 次</Typography.Text>
                  {row.retry_of_task_id ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      重试自 #{row.retry_of_task_id}
                    </Typography.Text>
                  ) : null}
                  {row.priority ? <Tag color="blue">优先级 {row.priority > 0 ? `+${row.priority}` : row.priority}</Tag> : null}
                </Space>
              ),
            },
            {
              title: '审查结论',
              key: 'review_conclusion',
              width: 116,
              render: (_, row) => reviewConclusionTag(row.review_conclusion),
            },
            {
              title: '结果完整性',
              key: 'completeness_status',
              width: 132,
              render: (_, row) => completenessTag(row.completeness_status),
            },
            {
              title: '人工状态',
              key: 'human_status',
              width: 126,
              render: (_, row) => humanStatusTag(row.human_status),
            },
            { title: '创建时间', dataIndex: 'created_at', width: 188 },
            {
              title: '审核耗时(分钟)',
              key: 'duration_ms',
              width: 132,
              align: 'right',
              render: (_, row) => formatDurationMinutes(row.duration_ms),
            },
            {
              title: '消耗词元',
              key: 'total_tokens',
              width: isAdmin ? 148 : 108,
              align: 'right',
              render: (_, row) => tokensCell(row, isAdmin),
            },
            {
              title: '操作',
              key: 'act',
              width: isAdmin ? 890 : 690,
              render: (_, row) => {
                const reviewable =
                  row.status === 'succeeded' || row.status === 'failed'
                const terminal = reviewable || row.status === 'canceled'
                const cancelable =
                  (row.status === 'pending' || row.status === 'processing') &&
                  !row.cancel_requested_at
                const retryable = row.status === 'failed' || row.status === 'canceled'
                const canExportAnnotated = reviewable && Boolean(row.output_object_key?.trim())
                const canExportReport = reportMayExist(row)
                return (
                  <Space size="middle" wrap={false}>
                    <Tooltip
                      title={
                        reviewable
                          ? undefined
                          : '任务处理结束后（已完成或失败）可进入人工审阅'
                      }
                    >
                      <Button
                        type="link"
                        size="small"
                        icon={<AuditOutlined />}
                        disabled={!reviewable}
                        onClick={() => navigate(`/review/${row.id}/manual`)}
                      >
                        人工审阅
                      </Button>
                    </Tooltip>
                    {(row.status === 'pending' || row.status === 'processing') ? (
                      <Popconfirm
                        title="取消该审核任务？"
                        description={row.status === 'processing' ? '处理中任务将在安全检查点停止，不会强制中断正在写入的文件。' : '排队中的任务会立即取消。'}
                        okText="确认取消"
                        cancelText="返回"
                        disabled={!cancelable}
                        onConfirm={() => cancelMut.mutate(row.id)}
                      >
                        <Tooltip title={row.cancel_requested_at ? '取消请求已提交，请等待任务停止' : undefined}>
                          <Button
                            type="link"
                            size="small"
                            danger
                            icon={<StopOutlined />}
                            disabled={!cancelable}
                            loading={cancelMut.isPending && cancelMut.variables === row.id}
                          >
                            {row.cancel_requested_at ? '取消中' : '取消'}
                          </Button>
                        </Tooltip>
                      </Popconfirm>
                    ) : null}
                    {retryable ? (
                      <Popconfirm
                        title="重新创建审核任务？"
                        description={`系统会复制原文件和附件，创建第 ${(row.attempt_no || 1) + 1} 次独立尝试。`}
                        okText="确认重试"
                        cancelText="取消"
                        onConfirm={() => retryMut.mutate(row.id)}
                      >
                        <Button
                          type="link"
                          size="small"
                          icon={<RedoOutlined />}
                          loading={retryMut.isPending && retryMut.variables === row.id}
                        >
                          重试
                        </Button>
                      </Popconfirm>
                    ) : null}
                    {isAdmin ? (
                      <Button
                        type="link"
                        size="small"
                        icon={<FileTextOutlined />}
                        onClick={() => void openReviewLog(row.id)}
                      >
                        审核日志
                      </Button>
                    ) : null}
                    <Button
                      type="link"
                      size="small"
                      icon={<HistoryOutlined />}
                      onClick={() => setArtifactTask(row)}
                    >
                      文档版本
                    </Button>
                    <Tooltip
                        title={canExportReport ? undefined : '尚未形成可导出的审核报告'}
                    >
                      <Button
                        type="link"
                        size="small"
                        icon={<ProfileOutlined />}
                        disabled={!canExportReport}
                        onClick={() => void handleAuditReportExport(row)}
                      >
                        审核报告
                      </Button>
                    </Tooltip>
                    <Tooltip
                        title={
                          canExportAnnotated
                            ? undefined
                            : '尚未生成带批注的审核方案，不能以原始文件代替审核结果'
                        }
                    >
                      <Button
                        type="link"
                        size="small"
                        icon={<ExportOutlined />}
                        disabled={!canExportAnnotated}
                        onClick={() => void handleExport(row)}
                      >
                        导出方案
                      </Button>
                    </Tooltip>
                    {isAdmin ? (
                      <Popconfirm
                        title="删除该审核任务？"
                        description="将移除任务记录及已上传的文档，且不可恢复。"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{
                          danger: true,
                          loading:
                            deleteMut.isPending &&
                            deleteMut.variables === row.id,
                        }}
                        onConfirm={() => deleteMut.mutate(row.id)}
                      >
                        <Button
                          type="link"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          disabled={!terminal}
                        >
                          删除
                        </Button>
                      </Popconfirm>
                    ) : null}
                  </Space>
                )
              },
            },
          ]}
        />
        </div>
      </PageShell>

      <Drawer
        title={artifactTask ? `文档版本 — 任务 #${artifactTask.id}` : '文档版本'}
        open={artifactTask !== null}
        width={760}
        destroyOnHidden
        onClose={() => {
          setArtifactTask(null)
          setDownloadingArtifactId(null)
        }}
      >
        {artifactTask ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Alert
              type="info"
              showIcon
              message={artifactTask.original_filename}
              description="原始方案、AI 批注版、专家编辑版和正式签发报告分别保存。已标记为不可变的版本只能下载，不能被后续编辑覆盖。"
            />

            {artifactsQuery.isLoading ? (
              <div style={{ padding: '48px 0', textAlign: 'center' }}>
                <Spin tip="正在读取文档版本…" />
              </div>
            ) : null}

            {artifactsQuery.isError ? (
              <Alert
                type="error"
                showIcon
                message="文档版本加载失败"
                description={formatApiErrorMessage(artifactsQuery.error, '无法读取该任务的文档版本')}
                action={<Button onClick={() => void artifactsQuery.refetch()}>重试</Button>}
              />
            ) : null}

            {!artifactsQuery.isLoading && !artifactsQuery.isError && artifactsQuery.data?.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                message="该任务没有文档版本记录"
                description="该任务可能创建于文档版本功能启用前，因此没有版本索引。这不表示任务文件已经丢失；如原有成果仍可用，可继续通过任务列表中的“审核报告”或“导出方案”下载。"
              />
            ) : null}

            {!artifactsQuery.isLoading && !artifactsQuery.isError
              ? artifactGroups.map((group) => (
                  <section
                    key={group.kind}
                    style={{
                      border: '1px solid #f0f0f0',
                      borderRadius: 8,
                      overflow: 'hidden',
                      background: '#fff',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 12,
                        padding: '12px 16px',
                        background: '#fafafa',
                        borderBottom: group.items.length ? '1px solid #f0f0f0' : undefined,
                      }}
                    >
                      <Space>
                        <Tag color={group.view.color}>{group.view.label}</Tag>
                        <Typography.Text type="secondary">{group.items.length} 个版本</Typography.Text>
                      </Space>
                    </div>

                    {group.items.length === 0 ? (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description={`尚未生成${group.view.label}`}
                        styles={{ image: { height: 32 } }}
                      />
                    ) : (
                      group.items.map((artifact, index) => (
                        <div
                          key={artifact.id}
                          style={{
                            padding: 16,
                            borderTop: index === 0 ? undefined : '1px solid #f0f0f0',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'flex-start',
                              gap: 16,
                            }}
                          >
                            <div style={{ minWidth: 0, flex: 1 }}>
                              <Space wrap size={[6, 6]}>
                                <Typography.Text strong>版本 v{artifact.version_no}</Typography.Text>
                                {artifact.immutable ? (
                                  <Tag color="success">不可变（已锁定）</Tag>
                                ) : (
                                  <Tag color="warning">可继续编辑</Tag>
                                )}
                                {artifact.review_round_id ? <Tag>复核轮次 #{artifact.review_round_id}</Tag> : null}
                              </Space>
                              <Typography.Paragraph
                                ellipsis={{ rows: 2, tooltip: artifact.original_filename }}
                                style={{ margin: '8px 0 4px' }}
                              >
                                {artifact.original_filename || '未命名文档'}
                              </Typography.Paragraph>
                              <Space wrap split={<Typography.Text type="secondary">·</Typography.Text>}>
                                <Typography.Text type="secondary">{formatArtifactTime(artifact.created_at)}</Typography.Text>
                                <Typography.Text type="secondary">{formatArtifactSize(artifact.size_bytes)}</Typography.Text>
                                <Typography.Text type="secondary">{artifact.content_type || '未知格式'}</Typography.Text>
                              </Space>
                            </div>
                            <Button
                              type="primary"
                              ghost
                              icon={<CloudDownloadOutlined />}
                              loading={downloadingArtifactId === artifact.id}
                              onClick={() => void handleArtifactDownload(artifact)}
                            >
                              下载
                            </Button>
                          </div>
                          <div style={{ marginTop: 10 }}>
                            <Typography.Text type="secondary">SHA256：</Typography.Text>
                            <Typography.Text
                              code
                              copyable={{ text: artifact.sha256 }}
                              style={{ wordBreak: 'break-all' }}
                            >
                              {artifact.sha256 || '未记录'}
                            </Typography.Text>
                          </div>
                          {artifact.supersedes_artifact_id ? (
                            <Typography.Text type="secondary" style={{ display: 'block', marginTop: 6 }}>
                              替代文档版本记录 #{artifact.supersedes_artifact_id}
                            </Typography.Text>
                          ) : null}
                        </div>
                      ))
                    )}
                  </section>
                ))
              : null}
          </Space>
        ) : null}
      </Drawer>

      <Modal
        title="提交方案审核"
        open={submitOpen}
        onCancel={() => {
          if (!submitMut.isPending) {
            setSubmitOpen(false)
            setSubmitIdempotencyKey('')
          }
        }}
        onOk={confirmSubmit}
        confirmLoading={submitMut.isPending}
        okText="提交"
        width={760}
        maskClosable={!submitMut.isPending}
        destroyOnClose
      >
        <p style={{ marginBottom: 12, color: 'rgba(0,0,0,0.55)', fontSize: 13 }}>
          系统会先将 Word 转为 PDF，再由 PaddleOCR PP-StructureV3 解析版面、表格和公式，随后创建异步审查任务。
        </p>
        <Form layout="vertical">
          <Form.Item label="方案类型" required>
            <Select
              disabled
              value={schemeId ?? undefined}
              options={withTemplate.map((s) => ({
                value: s.id,
                label: `${s.category} / ${s.name}`,
                disabled: !schemeIsReady(s),
              }))}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label="方案文件" required>
            <Upload.Dragger
              maxCount={1}
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              fileList={fileList}
              beforeUpload={(file) => {
                setFileList([
                  {
                    uid: file.uid,
                    name: file.name,
                    status: 'done',
                    originFileObj: file,
                  },
                ])
                return false
              }}
              onRemove={() => setFileList([])}
            >
              <p className="ant-upload-drag-icon">
                <UploadOutlined style={{ fontSize: 36, color: '#1677ff' }} />
              </p>
              <p className="ant-upload-text">点击或拖拽 .docx 到此处</p>
            </Upload.Dragger>
          </Form.Item>
          <Row gutter={[16, 0]}>
            <Col xs={24} md={16}>
              <Form.Item label="所属项目" required extra="审核任务将作为该项目的一个正式文档版本保存，专家复核可追溯项目与地区。">
                <Select
                  showSearch
                  optionFilterProp="label"
                  loading={projectsQuery.isLoading}
                  value={projectId ?? undefined}
                  placeholder="选择已有项目"
                  onChange={(value) => setProjectId(value)}
                  options={(projectsQuery.data ?? []).map((project) => ({
                    value: project.id,
                    label: `${project.name}${project.region ? `（${project.region}）` : ''}`,
                  }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="新项目">
                <Button block onClick={() => { projectForm.resetFields(); setNewProjectOpen(true) }}>
                  新建并选择项目
                </Button>
              </Form.Item>
            </Col>
          </Row>
          {projectsQuery.isError ? (
            <Alert
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
              message="项目列表加载失败"
              description={formatApiErrorMessage(projectsQuery.error, '请重试或新建项目。')}
              action={<Button size="small" onClick={() => void projectsQuery.refetch()}>重试</Button>}
            />
          ) : null}
          <Form.Item label="方案版本号" required extra="同一项目、同一方案类型下不可重复，例如 V1、V2-整改后。">
            <Input value={versionLabel} onChange={(event) => setVersionLabel(event.target.value)} maxLength={64} placeholder="V1" />
          </Form.Item>
          <Form.Item label="审查重点与补充说明（可选）">
            <Input.TextArea
              value={reviewFocus}
              onChange={(event) => setReviewFocus(event.target.value)}
              rows={3}
              maxLength={2000}
              showCount
              placeholder="例如：重点核验连墙件布置、基础承载力和现场图片中的架体搭设情况"
            />
          </Form.Item>
          {isAdmin ? (
            <Form.Item label="队列优先级" extra="范围 -10～10；普通任务保持 0，数值越大越优先。">
              <InputNumber min={-10} max={10} precision={0} value={priority} onChange={(value) => setPriority(value ?? 0)} />
            </Form.Item>
          ) : null}
          <Form.Item label="辅助文档（可选，最多10个）" extra="支持 DOCX、PDF；单个不超过30MB。将与主方案一起提供给 Dify。">
            <Upload
              multiple
              maxCount={10}
              accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              fileList={supportingFileList}
              beforeUpload={(file) => {
                setSupportingFileList((current) => [
                  ...current.filter((item) => item.uid !== file.uid),
                  { uid: file.uid, name: file.name, status: 'done' as const, originFileObj: file },
                ].slice(0, 10))
                return false
              }}
              onRemove={(file) => {
                setSupportingFileList((current) => current.filter((item) => item.uid !== file.uid))
              }}
            >
              <Button icon={<UploadOutlined />}>选择辅助文档</Button>
            </Upload>
          </Form.Item>
          <Form.Item label="现场图片（可选，最多20张）" extra="支持 JPG、PNG；单张不超过15MB。不映射 site_images 时 Dify 不接收，但系统仍会安全保存。">
            <Upload
              multiple
              maxCount={20}
              accept=".jpg,.jpeg,.png,image/jpeg,image/png"
              listType="picture"
              fileList={siteImageFileList}
              beforeUpload={(file) => {
                setSiteImageFileList((current) => [
                  ...current.filter((item) => item.uid !== file.uid),
                  { uid: file.uid, name: file.name, status: 'done' as const, originFileObj: file },
                ].slice(0, 20))
                return false
              }}
              onRemove={(file) => {
                setSiteImageFileList((current) => current.filter((item) => item.uid !== file.uid))
              }}
            >
              <Button icon={<UploadOutlined />}>选择现场图片</Button>
            </Upload>
          </Form.Item>
          <Alert
            type="info"
            showIcon
            message="重复点击或网络重试不会创建重复任务"
            description="本次提交使用同一个幂等标识；只有关闭窗口后重新发起，才会生成新的提交动作。"
          />
        </Form>
      </Modal>

      <Modal
        title="新建工程项目"
        open={newProjectOpen}
        onCancel={() => {
          setNewProjectOpen(false)
          projectForm.resetFields()
        }}
        onOk={() => projectForm.submit()}
        confirmLoading={createProjectMut.isPending}
        okText="创建并选择"
        destroyOnClose
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="项目资料会随版本进入审查与专家复核"
          description="项目所在地用于法规适用性判断；参建单位信息用于正式报告抬头和后续追溯。"
        />
        <Form<ProjectCreate>
          form={projectForm}
          layout="vertical"
          initialValues={{
            name: '',
            region: '',
            construction_unit: '',
            contractor: '',
            supervision_unit: '',
          }}
          onFinish={(values) => createProjectMut.mutate(values)}
        >
          <Form.Item name="name" label="项目名称" rules={[{ required: true, whitespace: true, message: '请输入项目名称' }]}>
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item name="region" label="项目所在地" rules={[{ required: true, whitespace: true, message: '请输入项目所在地' }]}>
            <Input maxLength={255} placeholder="例如：北京市海淀区" />
          </Form.Item>
          <Form.Item name="construction_unit" label="建设单位">
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item name="contractor" label="施工单位">
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item name="supervision_unit" label="监理单位">
            <Input maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={logModalTaskId ? `审核日志 — 任务 #${logModalTaskId}` : '审核日志'}
        open={logModalTaskId !== null}
        onCancel={() => {
          setLogModalTaskId(null)
          setLogContent(null)
        }}
        footer={null}
        width={720}
        destroyOnClose
      >
        {logLoading ? (
          <Typography.Text type="secondary">加载中…</Typography.Text>
        ) : (
          <pre
            style={{
              margin: 0,
              maxHeight: 'min(60vh, 480px)',
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
              fontSize: 12,
              lineHeight: 1.5,
              padding: 12,
              background: 'var(--ant-color-fill-quaternary, rgba(0,0,0,0.04))',
              borderRadius: 8,
            }}
          >
            {logContent ?? ''}
          </pre>
        )}
      </Modal>
    </div>
  )
}
