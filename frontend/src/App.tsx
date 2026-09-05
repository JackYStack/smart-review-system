import { App as AntApp, Spin } from 'antd'
import { useEffect, type ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import AppLayout from './components/AppLayout'
import { DEFAULT_FAVICON_SRC, DEFAULT_SYSTEM_NAME } from './config/brand'
import { useBranding } from './hooks/useBranding'
import BasisPage from './pages/BasisPage'
import LoginPage from './pages/LoginPage'
import ManualReviewPage from './pages/ManualReviewPage'
import ReviewEditPlaceholderPage from './pages/ReviewEditPlaceholderPage'
import ReviewPage from './pages/ReviewPage'
import SchemesPage from './pages/SchemesPage'
import SettingsPage from './pages/SettingsPage'
import TemplatesPage from './pages/TemplatesPage'
import DashboardPage from './pages/DashboardPage'
import HelpPage from './pages/HelpPage'
import UsersPage from './pages/UsersPage'
import ExpertReviewPoolPage from './pages/ExpertReviewPoolPage'
import ExpertReviewDetailPage from './pages/ExpertReviewDetailPage'
import RulesPage from './pages/RulesPage'
import { DEMO_MODE } from './demo/demoApi'
import { REVIEW_STAFF_ROLES } from './utils/expertReview'

function defaultPathForRole(role?: string): string {
  if (role === 'admin') return '/dashboard'
  if (role === 'expert' || role === 'review_admin') return '/expert-reviews'
  return '/review'
}

function RequireAuth({ children }: { children: ReactElement }) {
  const { user, loading, token } = useAuth()
  if (loading) {
    return (
      <div className="app-auth-loading" role="status" aria-live="polite">
        <Spin size="large" />
        <p className="app-auth-loading__hint">正在验证登录状态…</p>
      </div>
    )
  }
  if (!token || !user) {
    return <Navigate to="/login" replace />
  }
  return children
}

function RequireAdmin({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="app-auth-loading" role="status" aria-live="polite">
        <Spin size="large" />
        <p className="app-auth-loading__hint">正在验证登录状态…</p>
      </div>
    )
  }
  if (user?.role !== 'admin') {
    return <Navigate to={defaultPathForRole(user?.role)} replace />
  }
  return children
}

function RequireReviewStaff({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="app-auth-loading" role="status" aria-live="polite">
        <Spin size="large" />
        <p className="app-auth-loading__hint">正在验证复核权限…</p>
      </div>
    )
  }
  if (!user || !REVIEW_STAFF_ROLES.has(user.role)) {
    return <Navigate to="/review" replace />
  }
  return children
}

function DefaultIndexRedirect() {
  const { user } = useAuth()
  if (DEMO_MODE) {
    return <Navigate to="/review" replace />
  }
  return <Navigate to={defaultPathForRole(user?.role)} replace />
}

function AppRoutes() {
  const { user, loading, token } = useAuth()
  const { branding } = useBranding()

  useEffect(() => {
    document.title = branding.systemName || DEFAULT_SYSTEM_NAME

    let favicon = document.querySelector<HTMLLinkElement>("link[rel='icon']")
    if (!favicon) {
      favicon = document.createElement('link')
      favicon.rel = 'icon'
      document.head.appendChild(favicon)
    }
    favicon.href = branding.faviconSrc || DEFAULT_FAVICON_SRC
  }, [branding.faviconSrc, branding.systemName])

  return (
    <Routes>
      <Route
        path="/login"
        element={
          loading ? (
            <div className="app-auth-loading" role="status" aria-live="polite">
              <Spin size="large" />
              <p className="app-auth-loading__hint">加载中…</p>
            </div>
          ) : token && user ? (
            <Navigate
              to={DEMO_MODE ? '/review' : defaultPathForRole(user.role)}
              replace
            />
          ) : (
            <LoginPage />
          )
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DefaultIndexRedirect />} />
        <Route
          path="dashboard"
          element={
            <RequireAdmin>
              <DashboardPage />
            </RequireAdmin>
          }
        />
        <Route
          path="schemes"
          element={
            <RequireAdmin>
              <SchemesPage />
            </RequireAdmin>
          }
        />
        <Route path="review" element={<ReviewPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route path="review/:taskId/manual" element={<ManualReviewPage />} />
        <Route path="review/:taskId/edit" element={<ReviewEditPlaceholderPage />} />
        <Route path="review/:taskId/preview" element={<ReviewEditPlaceholderPage />} />
        <Route
          path="expert-reviews"
          element={
            <RequireReviewStaff>
              <ExpertReviewPoolPage />
            </RequireReviewStaff>
          }
        />
        <Route
          path="expert-reviews/:roundId"
          element={
            <RequireReviewStaff>
              <ExpertReviewDetailPage />
            </RequireReviewStaff>
          }
        />
        <Route
          path="basis"
          element={
            <RequireAdmin>
              <BasisPage />
            </RequireAdmin>
          }
        />
        <Route
          path="templates"
          element={
            <RequireAdmin>
              <TemplatesPage />
            </RequireAdmin>
          }
        />
        <Route
          path="rules"
          element={
            <RequireAdmin>
              <RulesPage />
            </RequireAdmin>
          }
        />
        <Route
          path="settings"
          element={
            <RequireAdmin>
              <SettingsPage />
            </RequireAdmin>
          }
        />
        <Route
          path="users"
          element={
            <RequireAdmin>
              <UsersPage />
            </RequireAdmin>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AntApp>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </AntApp>
  )
}
