import api from './api'

export interface RecentEventItem {
  id: number
  event_id: string
  title: string
  severity_text: string
  status: string
  source: string
  created_at: string
}

export interface DashboardSummary {
  total_events_24h: number
  total_events_7d: number
  critical_pending: number
  events_by_severity: Record<string, number>
  avg_ttd_seconds: number | null
  avg_ttr_seconds: number | null
  false_positive_rate: number
  events_auto_resolved: number
  events_failed: number
  active_integrations: number
  active_knowledge_bases: number
  active_db_connections: number
  llm_status: string
  system_status: string
  recent_events: RecentEventItem[]
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res = await api.get('/dashboard/summary')
  return res.data
}
