import api from './api'

export interface Model {
    id: string
    name: string
    base_model_id: string
    description?: string
    tags: string[]
    system_prompt?: string
    params: Record<string, any>
    knowledge_ids: number[]
    tool_ids: number[]
    skill_ids: number[]
    capabilities: Record<string, boolean>
    default_features: Record<string, boolean>
    builtin_tools: Record<string, boolean>
    tts_voice?: string
}

export type ModelCreate = Model
export type ModelUpdate = Partial<Model>

const modelService = {
    async listModels(): Promise<Model[]> {
        const response = await api.get('/api/v1/models')
        return response.data
    },

    async getModel(id: string): Promise<Model> {
        const response = await api.get(`/api/v1/models/${id}`)
        return response.data
    },

    async createModel(model: ModelCreate): Promise<Model> {
        const response = await api.post('/api/v1/models', model)
        return response.data
    },

    async updateModel(id: string, model: ModelUpdate): Promise<Model> {
        const response = await api.put(`/api/v1/models/${id}`, model)
        return response.data
    },

    async deleteModel(id: string): Promise<void> {
        await api.delete(`/api/v1/models/${id}`)
    },

    async listProviders(): Promise<any[]> {
        const response = await api.get('/api/v1/models/discovery/providers')
        return response.data
    },

    async listProviderModels(providerId: string): Promise<any[]> {
        const response = await api.get(`/api/v1/models/discovery/models/${providerId}`)
        return response.data
    }
}

export default modelService
