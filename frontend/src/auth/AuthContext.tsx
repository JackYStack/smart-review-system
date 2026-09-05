import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import type { UserPublic } from '../api/types'
import { DEMO_MODE } from '../demo/demoApi'

const DEMO_USER: UserPublic = {
  id: 1,
  username: '演示管理员',
  phone: 'demo',
  role: 'admin',
}

interface AuthState {
  user: UserPublic | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(DEMO_MODE ? DEMO_USER : null)
  const [token, setToken] = useState<string | null>(() =>
    DEMO_MODE ? 'local-demo-token' : localStorage.getItem('token'),
  )
  const [loading, setLoading] = useState(!DEMO_MODE)

  const refresh = useCallback(async () => {
    if (DEMO_MODE) {
      setUser(DEMO_USER)
      setToken('local-demo-token')
      return
    }
    const t = localStorage.getItem('token')
    if (!t) {
      setUser(null)
      setToken(null)
      return
    }
    const { data } = await api.get<UserPublic>('/auth/me')
    setUser(data)
    setToken(t)
  }, [])

  useEffect(() => {
    if (DEMO_MODE) return
    ;(async () => {
      try {
        if (localStorage.getItem('token')) await refresh()
      } catch {
        localStorage.removeItem('token')
        setUser(null)
        setToken(null)
      } finally {
        setLoading(false)
      }
    })()
  }, [refresh])

  const login = useCallback(async (username: string, password: string) => {
    if (DEMO_MODE) {
      setUser(DEMO_USER)
      setToken('local-demo-token')
      return
    }
    const { data } = await api.post<{ access_token: string }>('/auth/login', {
      username,
      password,
    })
    localStorage.setItem('token', data.access_token)
    setToken(data.access_token)
    await refresh()
  }, [refresh])

  const logout = useCallback(() => {
    if (DEMO_MODE) {
      setUser(DEMO_USER)
      setToken('local-demo-token')
      return
    }
    localStorage.removeItem('token')
    setUser(null)
    setToken(null)
  }, [])

  const value = useMemo(
    () => ({ user, token, loading, login, logout, refresh }),
    [user, token, loading, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
