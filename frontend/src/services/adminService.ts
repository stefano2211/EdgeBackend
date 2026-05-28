import api from './api'

export interface AdminUser {
    id: string
    username: string
    email: string
    is_active: boolean
    is_superuser: boolean
    created_at: string
    updated_at: string
}

export interface DailyMessages {
    date: string
    count: number
}

export interface ModelUsageItem {
    rank: number
    model: string
    messages: number
    tokens: number
    percentage: number
}

export interface UserActivityItem {
    rank: number
    username: string
    email: string
    messages: number
    tokens: number
}

export interface AnalyticsData {
    total_messages: number
    total_tokens: number
    total_chats: number
    total_users: number
    daily_messages: DailyMessages[]
    model_usage: ModelUsageItem[]
    user_activity: UserActivityItem[]
}

export interface SystemSettingsGeneral {
    auth_default_user_role: string
    auth_enable_sign_ups: boolean
    feature_enable_api_keys: boolean
    feature_jwt_expiration: string
    feature_enable_community_sharing: boolean
    ollama_enabled: boolean
    ollama_base_url: string
    openrouter_enabled: boolean
    openrouter_api_key?: string
    openrouter_base_url: string
}

export interface SystemSettings {
    document_chunk_size: number
    document_chunk_overlap: number
    retrieval_search_results: number
}

export const adminService = {
    async listUsers(): Promise<AdminUser[]> {
        const response = await api.get('/api/v1/admin/users')
        return response.data
    },

    async updateUserRole(userId: string, isSuperuser: boolean): Promise<AdminUser> {
        const response = await api.put(`/api/v1/admin/users/${userId}/role`, {
            is_superuser: isSuperuser
        })
        return response.data
    },

    async deleteUser(userId: string): Promise<void> {
        await api.delete(`/api/v1/admin/users/${userId}`)
    },

    async getAnalytics(days: number = 7): Promise<AnalyticsData> {
        const response = await api.get('/api/v1/admin/stats', { params: { days } })
        return response.data
    },

    async getGeneralSettings(): Promise<SystemSettingsGeneral> {
        const response = await api.get('/api/v1/admin/settings/general')
        return response.data as SystemSettingsGeneral
    },

    async updateGeneralSettings(settings: SystemSettingsGeneral): Promise<SystemSettingsGeneral> {
        const response = await api.put('/api/v1/admin/settings/general', settings)
        return response.data as SystemSettingsGeneral
    },

    async getSettings(): Promise<SystemSettings> {
        const response = await api.get('/api/v1/admin/settings/documents')
        return response.data as SystemSettings
    },

    async updateSettings(settings: SystemSettings): Promise<SystemSettings> {
        const response = await api.put('/api/v1/admin/settings/documents', settings)
        return response.data as SystemSettings
    }
}
