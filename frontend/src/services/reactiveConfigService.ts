import api from './api'

export interface ReactiveTool {
  id: number
  name: string
  description: string | null
  source_name: string | null
  is_enabled: boolean
}

export interface ReactiveKnowledgeBase {
  id: string
  name: string
  description: string | null
  document_count: number
  is_enabled_reactive: boolean
}

const reactiveConfigService = {
  async listTools(): Promise<ReactiveTool[]> {
    const response = await api.get('/api/v1/reactive/tools')
    const data = response.data
    return Array.isArray(data) ? data : (data.items || [])
  },

  async toggleTool(toolId: number, isEnabled: boolean): Promise<void> {
    await api.put(`/api/v1/reactive/tools/${toolId}`, { is_enabled: isEnabled })
  },

  async listKnowledgeBases(): Promise<ReactiveKnowledgeBase[]> {
    // Now reads from unified knowledge bases endpoint
    const response = await api.get('/api/v1/knowledge')
    const data = response.data
    const kbs = Array.isArray(data) ? data : (data.items || [])
    // Map to reactive format: all KBs are shown, with their reactive toggle state
    return kbs.map((kb: any) => ({
      id: String(kb.id),
      name: kb.name,
      description: kb.description,
      document_count: kb.documents?.length || 0,
      is_enabled_reactive: kb.is_enabled_reactive,
    }))
  },

  async toggleKnowledgeBase(kbId: string, isEnabled: boolean): Promise<void> {
    await api.patch(`/api/v1/knowledge/${kbId}/toggle-reactive`, null, {
      params: { enabled: isEnabled }
    })
  },
}

export default reactiveConfigService
