/**
 * Service for managing reactive credentials (encrypted secrets for agent automation).
 */
import api from './api'

export interface ReactiveCredential {
  id: number
  name: string
  key_identifier: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface CredentialCreatePayload {
  name: string
  key_identifier: string
  value: string
  description?: string
}

export const reactiveCredentialService = {
  async list(): Promise<ReactiveCredential[]> {
    const response = await api.get('/api/v1/reactive/credentials')
    return response.data
  },

  async create(data: CredentialCreatePayload): Promise<ReactiveCredential> {
    const response = await api.post('/api/v1/reactive/credentials', data)
    return response.data
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/api/v1/reactive/credentials/${id}`)
  },
}
