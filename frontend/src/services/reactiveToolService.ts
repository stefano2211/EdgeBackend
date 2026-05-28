import api from './api'

export interface ReactiveMCPSource {
    id: number
    user_id: number
    name: string
    description: string | null
    url: string
    type: string
    is_enabled: boolean
    created_at: string
}

export interface ReactiveToolConfig {
    id: number
    user_id: number
    name: string
    description: string | null
    is_enabled: boolean
    config: Record<string, any> | null
    parameter_schema: Record<string, any> | null
    source_id: number | null
    created_at: string
    updated_at: string
}

export const reactiveToolService = {
    // Sources
    async listSources() {
        const response = await api.get('/api/v1/reactive/tools/sources/')
        return response.data as ReactiveMCPSource[]
    },

    async createSource(data: { name: string; url: string; type?: string; description?: string }) {
        const response = await api.post('/api/v1/reactive/tools/sources/', data)
        return response.data as ReactiveMCPSource
    },

    async deleteSource(id: number) {
        await api.delete(`/api/v1/reactive/tools/sources/${id}`)
    },

    // Tools
    async listTools() {
        const response = await api.get('/api/v1/reactive/tools')
        return response.data as ReactiveToolConfig[]
    },

    async createTool(data: Partial<ReactiveToolConfig>) {
        const response = await api.post('/api/v1/reactive/tools', data)
        return response.data as ReactiveToolConfig
    },

    async deleteTool(id: number) {
        await api.delete(`/api/v1/reactive/tools/${id}`)
    },

}
