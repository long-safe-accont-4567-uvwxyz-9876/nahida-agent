const BASE = '/api/v1'

interface ApiEnvelope<T> {
  ok: boolean
  data: T | null
  error?: { code: string; message: string }
}

async function request<T>(path: string, options?: RequestInit, confirm = false): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(confirm ? { 'X-Confirm': 'yes' } : {}),
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    if (!location.hash.includes('login')) location.hash = '#/login'
    throw new Error('登录已过期，请重新登录')
  }
  let body: ApiEnvelope<T>
  try {
    body = await res.json()
  } catch {
    throw new Error(`HTTP ${res.status}`)
  }
  if (!res.ok || !body.ok) {
    const msg = body?.error?.message || (body as any)?.detail || `HTTP ${res.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return body.data as T
}

export const get = <T = any>(path: string) => request<T>(path)
export const post = <T = any>(path: string, body?: unknown, confirm = false) =>
  request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }, confirm)
export const put = <T = any>(path: string, body?: unknown, confirm = false) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body ?? {}) }, confirm)
export const del = <T = any>(path: string, confirm = false) =>
  request<T>(path, { method: 'DELETE' }, confirm)

export const api = {
  login: (password: string) =>
    post<{ token: string; expires_at: number }>('/auth/login', { password }),

  getStatus: () => get('/system/status'),
  getSessions: () => get<any[]>('/sessions'),
  createSession: () => post<{ session_id: string }>('/sessions'),
  deleteSession: (id: string) => del(`/sessions/${id}`),
  getMessages: (sessionId: string, before = 0, limit = 50) =>
    get<any[]>(`/sessions/${sessionId}/messages?before=${before}&limit=${limit}`),
  getCommands: () => get<Array<{ name: string; description: string; owner_only: boolean }>>('/commands'),

  getAgents: () => get<any[]>('/agents'),
  getPermissions: (name: string) => get(`/agents/${name}/permissions`),

  tts: (text: string, voice?: string, style?: string) =>
    post<{ audio_url: string; cached: boolean }>('/media/tts', { text, voice, style }),
}

export function exportSessionUrl(sessionId: string): string {
  return `${BASE}/sessions/${sessionId}/export`
}
