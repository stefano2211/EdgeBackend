import api from './api'

export interface WebhookSource {
  id: number
  user_id: number
  name: string
  slug: string
  description: string | null
  is_enabled: boolean
  mapping_config: Record<string, any> | null
  auto_discovered: boolean
  domain: string | null
  rate_limit_rpm: number
  last_payload_preview: Record<string, any> | null
  last_received_at: string | null
  total_received: number
  created_at: string
  updated_at: string
}

export interface WebhookCreatePayload {
  name: string
  slug: string
  description?: string
  is_enabled?: boolean
  mapping_config?: Record<string, any>
  rate_limit_rpm?: number
  domain?: string | null
}

export interface WebhookUpdatePayload {
  name?: string
  description?: string
  is_enabled?: boolean
  mapping_config?: Record<string, any>
  rate_limit_rpm?: number
  domain?: string | null
}

export interface WebhookTestResult {
  mapping_used: Record<string, any> | null
  auto_discovered: boolean
  extracted_fields: Record<string, any>
  body_preview: Record<string, any>
  would_create_event: boolean
}

export const webhookService = {
  async list(): Promise<WebhookSource[]> {
    const res = await api.get('/api/v1/webhooks')
    return res.data
  },

  async get(slug: string): Promise<WebhookSource> {
    const res = await api.get(`/api/v1/webhooks/${slug}`)
    return res.data
  },

  async create(data: WebhookCreatePayload): Promise<WebhookSource> {
    const res = await api.post('/api/v1/webhooks', data)
    return res.data
  },

  async update(slug: string, data: WebhookUpdatePayload): Promise<WebhookSource> {
    const res = await api.patch(`/api/v1/webhooks/${slug}`, data)
    return res.data
  },

  async delete(slug: string): Promise<void> {
    await api.delete(`/api/v1/webhooks/${slug}`)
  },

  async test(slug: string, payload: Record<string, any>): Promise<WebhookTestResult> {
    const res = await api.post(`/api/v1/webhooks/${slug}/test`, { payload })
    return res.data
  }
}
