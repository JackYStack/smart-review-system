import axios from 'axios'
import { DEMO_MODE, demoAdapter } from '../demo/demoApi'
import type { DocumentArtifact, DownloadUrlResponse } from './types'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000,
  ...(DEMO_MODE ? { adapter: demoAdapter } : {}),
})

export async function getReviewTaskArtifacts(taskId: number): Promise<DocumentArtifact[]> {
  const { data } = await api.get<DocumentArtifact[]>(`/review-tasks/${taskId}/artifacts`)
  return data
}

export async function getReviewArtifactDownloadUrl(
  taskId: number,
  artifactId: number,
): Promise<DownloadUrlResponse> {
  const { data } = await api.get<DownloadUrlResponse>(
    `/review-tasks/${taskId}/artifacts/${artifactId}/download-url`,
  )
  return data
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)
