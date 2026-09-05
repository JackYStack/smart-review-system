import type { ExpertReviewRound, UserRole } from '../api/types'
import { REVIEW_STEP_LABELS } from './reviewDisplay'

export const REVIEW_STAFF_ROLES = new Set<UserRole>(['expert', 'review_admin', 'admin'])
export const REVIEW_MANAGER_ROLES = new Set<UserRole>(['review_admin', 'admin'])

export const ROUND_STATUS_META: Record<string, { label: string; color: string }> = {
  pending_ai: { label: '等待AI审查', color: 'default' },
  pending: { label: '待领取', color: 'processing' },
  in_review: { label: '复核中', color: 'warning' },
  changes_requested: { label: '已退回整改', color: 'error' },
  pending_recheck: { label: '等待复审版本', color: 'purple' },
  approved: { label: '已批准待签发', color: 'success' },
  signed: { label: '已签发', color: 'green' },
}

export const DISPOSITION_META: Record<string, { label: string; color: string }> = {
  pending: { label: '待处置', color: 'default' },
  accepted: { label: '确认问题成立', color: 'error' },
  rejected: { label: '驳回AI问题', color: 'success' },
  modified: { label: '修改问题等级', color: 'warning' },
  resolved: { label: '确认已整改', color: 'blue' },
}

export const SEVERITY_META: Record<string, { label: string; color: string }> = {
  error: { label: '严重', color: 'red' },
  warning: { label: '警告', color: 'gold' },
  info: { label: '提示', color: 'blue' },
}

export const REVIEW_CONCLUSION_LABELS: Record<string, string> = {
  passed: '通过',
  conditional_pass: '有条件通过',
  changes_required: '需整改',
  rejected: '不通过',
  issues_found: 'AI发现问题',
  not_reviewed: 'AI未形成结论',
}

export const COMPLETENESS_LABELS: Record<string, string> = {
  complete: '完整',
  partial: '部分完成',
  degraded: '降级结果',
  unavailable: '不可用',
}

export const STEP_LABELS = REVIEW_STEP_LABELS

export function roundStatusMeta(status: string) {
  return ROUND_STATUS_META[status] ?? { label: status || '未知状态', color: 'default' }
}

export function canClaimRound(round: ExpertReviewRound): boolean {
  return round.status === 'pending' || round.status === 'in_review'
}

export function claimIsActive(round: ExpertReviewRound): boolean {
  if (!round.assigned_expert_id || !round.claim_expires_at) return false
  const expiresAt = new Date(round.claim_expires_at).getTime()
  return Number.isFinite(expiresAt) && expiresAt > Date.now()
}

export function formatReviewTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function hasIssueLocation(anchor: Record<string, unknown>): boolean {
  if (!anchor || Object.keys(anchor).length === 0) return false
  return [
    anchor.title_path,
    anchor.chapter,
    anchor.user_title,
    anchor.heading_para_index,
    anchor.template_node_id,
  ].some((value) => {
    if (Array.isArray(value)) return value.length > 0
    return value !== undefined && value !== null && String(value).trim().length > 0
  })
}

export function issueLocationText(anchor: Record<string, unknown>): string {
  const path = anchor.title_path
  if (Array.isArray(path) && path.length > 0) {
    return path.map((item) => String(item)).filter(Boolean).join(' > ')
  }
  for (const key of ['chapter', 'user_title']) {
    const value = anchor[key]
    if (value !== undefined && value !== null && String(value).trim()) return String(value).trim()
  }
  const paragraph = anchor.heading_para_index
  if (paragraph !== undefined && paragraph !== null && String(paragraph).trim()) {
    return `段落索引 ${String(paragraph).trim()}`
  }
  return '未定位到原文章节或段落'
}
