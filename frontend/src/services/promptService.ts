import api from './api'

export interface Prompt {
    id: string
    title: string
    description?: string
    query?: string
    icon?: string
    is_enabled: boolean
    system_prompt?: string
    temperature?: number | null
    max_tokens?: number | null
    top_p?: number | null
    top_k?: number | null
    seed?: number | null
    stop_sequence?: string
    is_active?: boolean
    created_at: string
    updated_at: string
}

export interface PromptCreate {
    title: string
    description?: string
    query?: string
    icon?: string
    is_enabled?: boolean
    system_prompt?: string
    temperature?: number | null
    max_tokens?: number | null
    top_p?: number | null
    top_k?: number | null
    seed?: number | null
    stop_sequence?: string
}

export interface PromptUpdate extends Partial<PromptCreate> {
    is_active?: boolean
}

const promptService = {
    async listPrompts(onlyEnabled = false): Promise<Prompt[]> {
        const response = await api.get('/api/v1/prompts', { params: { only_enabled: onlyEnabled } })
        return response.data
    },

    async createPrompt(prompt: PromptCreate): Promise<Prompt> {
        const response = await api.post('/api/v1/prompts', prompt)
        return response.data
    },

    async updatePrompt(id: string, prompt: PromptUpdate): Promise<Prompt> {
        const response = await api.patch(`/api/v1/prompts/${id}`, prompt)
        return response.data
    },

    async deletePrompt(id: string): Promise<void> {
        await api.delete(`/api/v1/prompts/${id}`)
    }
}

export default promptService
