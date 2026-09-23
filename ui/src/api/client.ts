import { useAuthStore } from '../stores/auth'
import { router } from '../router'

let refreshing: Promise<boolean> | null = null

async function refreshToken(): Promise<boolean> {
  const auth = useAuthStore()
  if (!auth.creds) return false
  try {
    const res = await fetch('/oauth/v2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ grant_type: 'refresh_token', ...auth.creds }),
    })
    const data = await res.json()
    if (!data.access_token) return false
    auth.setToken(data.access_token, data.api_domain || '')
    return true
  } catch {
    return false
  }
}

export async function apiFetch(path: string, options: RequestInit = {}, retried = false): Promise<any> {
  const auth = useAuthStore()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  }
  if (auth.token) headers['Authorization'] = `Zoho-oauthtoken ${auth.token}`
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json'

  const res = await fetch(path, { ...options, headers })

  if (res.status === 401) {
    if (!retried) {
      refreshing = refreshing || refreshToken().finally(() => { refreshing = null })
      if (await refreshing) return apiFetch(path, options, true)
    }
    auth.logout()
    router.push({ name: 'login' })
    throw new Error('Session expired')
  }

  if (res.status === 204) return null

  const text = await res.text()
  let data: any = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }

  if (!res.ok && data?.code) {
    throw new Error(data.message || data.code)
  }
  return data
}
