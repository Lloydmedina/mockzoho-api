import { apiFetch } from './client'

export async function getToken(params: Record<string, string>) {
  const body = new URLSearchParams(params)
  const res = await fetch('/oauth/v2/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  return res.json()
}

export async function listRecords(module: string, params: Record<string, any> = {}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v != null) qs.set(k, String(v))
  const data = await apiFetch(`/crm/v3/${module}?${qs}`)
  return data || { data: [], info: { count: 0, more_records: false } }
}

export async function getRecord(module: string, id: string) {
  const data = await apiFetch(`/crm/v3/${module}/${id}`)
  return data?.data?.[0] || null
}

export async function getRelated(module: string, id: string, related: string) {
  const data = await apiFetch(`/crm/v3/${module}/${id}/${related}`)
  return data?.data || []
}

export async function createRecord(module: string, record: Record<string, any>) {
  return apiFetch(`/crm/v3/${module}`, {
    method: 'POST',
    body: JSON.stringify({ data: [record] }),
  })
}

export async function updateRecord(module: string, id: string, record: Record<string, any>) {
  return apiFetch(`/crm/v3/${module}/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ data: [{ id, ...record }] }),
  })
}

export async function deleteRecord(module: string, id: string) {
  return apiFetch(`/crm/v3/${module}?ids=${id}`, { method: 'DELETE' })
}

export async function getModuleSchemas() {
  const data = await apiFetch('/__mock__/modules')
  return data?.modules || {}
}

export async function resetDatabase() {
  return apiFetch('/__mock__/reset', { method: 'POST' })
}
