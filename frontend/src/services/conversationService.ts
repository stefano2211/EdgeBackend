import api from './api'

export interface Conversation {
    id: string
    thread_id: string
    title: string
    is_archived: boolean
    created_at: string
    updated_at: string
}

export interface MessageItem {
    role: 'user' | 'assistant'
    content: string
    reasoning_content?: string | null
}

export const conversationService = {
    async list(): Promise<Conversation[]> {
        const response = await api.get('/api/v1/conversations')
        return response.data
    },

    async create(title: string = 'New Chat'): Promise<Conversation> {
        const response = await api.post('/api/v1/conversations', { title })
        return response.data
    },

    async getMessages(threadId: string): Promise<MessageItem[]> {
        const response = await api.get(`/api/v1/conversations/${threadId}/messages`)
        return response.data
    },

    async remove(threadId: string): Promise<void> {
        await api.delete(`/api/v1/conversations/${threadId}`)
    },

    async archive(threadId: string, archive: boolean = true): Promise<void> {
        await api.patch(`/api/v1/conversations/${threadId}/archive?archive=${archive}`)
    },

    async listArchived(): Promise<Conversation[]> {
        const response = await api.get('/api/v1/conversations?include_archived=true')
        return (response.data as Conversation[]).filter(c => c.is_archived)
    }
}
