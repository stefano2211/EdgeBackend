import api from './api'

export interface SystemStats {
    active_users: number
    total_conversations: number
    status: string
}

export const systemService = {
    async getStats(): Promise<SystemStats> {
        const response = await api.get('/api/v1/system/stats')
        return response.data
    }
}
