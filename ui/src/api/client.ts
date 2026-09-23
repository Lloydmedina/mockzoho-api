import { useAuthStore } from '../stores/auth'
import { router } from '../router'

export async function apiFetch(path: string, options: RequestInit = {}): Promise<any> {
  const auth = useAuthStore()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  }
  if (auth.token) headers['Authorization'] = `Zoho-oauthtoken ${auth.token}`
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json'

  const res = await fetch(path, { ...options, headers })

  if (res.status === 401) {
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
