import api from './api'

export interface KnowledgeDocument {
    id: string
    file_id: string
    filename: string
    status: string
    created_at: string
}

export interface KnowledgeBase {
    id: string
    user_id: string
    name: string
    description: string
    is_enabled_chat: boolean
    is_enabled_reactive: boolean
    created_at: string
    updated_at: string
}

export interface KnowledgeBaseDetail extends KnowledgeBase {
    documents: KnowledgeDocument[]
}

export const knowledgeService = {
    async createKnowledgeBase(name: string, description: string = '', isEnabledChat: boolean = true, isEnabledReactive: boolean = false) {
        const response = await api.post('/api/v1/knowledge', { 
            name, 
            description,
            is_enabled_chat: isEnabledChat,
            is_enabled_reactive: isEnabledReactive
        })
        return response.data as KnowledgeBase
    },

    async listKnowledgeBases() {
        const response = await api.get('/api/v1/knowledge')
        return response.data as KnowledgeBase[]
    },

    async getKnowledgeBase(id: string) {
        const response = await api.get(`/api/v1/knowledge/${id}`)
        return response.data as KnowledgeBaseDetail
    },

    async updateKnowledgeBase(id: string, name?: string, description?: string) {
        const response = await api.patch(`/api/v1/knowledge/${id}`, { name, description })
        return response.data as KnowledgeBase
    },

    async deleteKnowledgeBase(id: string) {
        await api.delete(`/api/v1/knowledge/${id}`)
    },

    async toggleChat(id: string, enabled: boolean) {
        const response = await api.patch(`/api/v1/knowledge/${id}/toggle-chat`, null, {
            params: { enabled }
        })
        return response.data as KnowledgeBase
    },

    async toggleReactive(id: string, enabled: boolean) {
        const response = await api.patch(`/api/v1/knowledge/${id}/toggle-reactive`, null, {
            params: { enabled }
        })
        return response.data as KnowledgeBase
    },

    // A helper function to upload document to a specific KB
    async uploadDocumentToKnowledgeBase(kbId: string, file: File) {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('knowledge_base_id', kbId)

        // Using backend's unified /upload endpoint handled in documents.py
        const response = await api.post('/api/v1/documents/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })

        return response.data
    }
}
