export const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://localhost:8005').replace(/\/$/, '')

export type RunSummary = {
  run_id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  ticker: string
  analysis_date: string
  created_at: string
  progress: number
  cancel_requested: boolean
}

export type RunDetail = RunSummary & {
  started_at?: string
  ended_at?: string
  error?: string
  report_dir?: string
  report_files: string[]
}

export type RunEvent = {
  id: number
  run_id: string
  ts: string
  event_type: string
  payload: Record<string, any>
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
