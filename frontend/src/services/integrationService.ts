import api from './api'

export interface IntegrationCatalog {
    id: number
    slug: string
    name: string
    description: string | null
    icon_url: string | null
    category: string | null
    source_type: string
    command: string | null
    args: string[] | null
    env_prefix: string | null
    auth_type: string
    auth_env_var_mapping: Record<string, string> | null
    auth_setup_guide_markdown: string | null
    is_enabled: boolean
    created_at: string
    updated_at: string
}

export interface IntegrationInstance {
    id: number
    user_id: number
    catalog_id: number
    instance_name: string
    is_enabled: boolean
    process_pid: number | null
    process_status: string | null
    last_used_at: string | null
    available_in_chat: boolean
    available_in_reactive: boolean
    mcp_source_id: number | null
    reactive_mcp_source_id: number | null
    catalog: IntegrationCatalog | null
    created_at: string
    updated_at: string
}

export interface IntegrationCredential {
    id: number
    instance_id: number
    credential_key: string
    expires_at: string | null
    created_at: string
}

export interface SetupGuide {
    catalog_name: string
    setup_guide_markdown: string
    required_fields: string[]
    auth_type: string
}

export interface MCPRegistryItem {
    id: number
    name: string
    description: string | null
    source_name: string
    source_type: string
    context: string
    transport: string
    is_enabled: boolean
    category: string | null
    instance_name: string | null
    created_at: string
}

export interface ProcessStatus {
    pid: number
    status: string
    command: string[]
}

export interface InstanceStatus {
    instance: IntegrationInstance
    process: ProcessStatus | null
}

export const integrationService = {
    // --- Catalog ---
    async listCatalog(): Promise<IntegrationCatalog[]> {
        const response = await api.get('/api/v1/integrations/catalog')
        return response.data
    },

    async getCatalogItem(slug: string): Promise<IntegrationCatalog> {
        const response = await api.get(`/api/v1/integrations/catalog/${slug}`)
        return response.data
    },

    // --- Instances ---
    async listInstances(): Promise<IntegrationInstance[]> {
        const response = await api.get('/api/v1/integrations/instances')
        return response.data
    },

    async createInstance(data: {
        catalog_slug: string
        instance_name: string
        available_in_chat?: boolean
        available_in_reactive?: boolean
    }): Promise<IntegrationInstance> {
        const response = await api.post('/api/v1/integrations/instances', data)
        return response.data
    },

    async getInstance(id: number): Promise<IntegrationInstance> {
        const response = await api.get(`/api/v1/integrations/instances/${id}`)
        return response.data
    },

    async updateInstance(id: number, data: {
        instance_name?: string
        is_enabled?: boolean
        available_in_chat?: boolean
        available_in_reactive?: boolean
    }): Promise<IntegrationInstance> {
        const response = await api.patch(`/api/v1/integrations/instances/${id}`, data)
        return response.data
    },

    async deleteInstance(id: number): Promise<void> {
        await api.delete(`/api/v1/integrations/instances/${id}`)
    },

    // --- Setup & Credentials ---
    async getSetupGuide(id: number): Promise<SetupGuide> {
        const response = await api.get(`/api/v1/integrations/instances/${id}/setup-guide`)
        return response.data
    },

    async submitCredentials(id: number, credentials: Record<string, string>): Promise<IntegrationInstance> {
        const response = await api.post(`/api/v1/integrations/instances/${id}/credentials`, { credentials })
        return response.data
    },

    async startOAuth(
        id: number,
        provider: string,
    ): Promise<{ authorization_url: string; state: string }> {
        const response = await api.post(`/api/v1/integrations/instances/${id}/oauth/${provider}/start`, {})
        return response.data
    },

    // --- Lifecycle ---
    async stopInstance(id: number): Promise<IntegrationInstance> {
        const response = await api.post(`/api/v1/integrations/instances/${id}/stop`)
        return response.data
    },

    async getStatus(id: number): Promise<InstanceStatus> {
        const response = await api.get(`/api/v1/integrations/instances/${id}/status`)
        return response.data
    },

    async syncInstance(id: number): Promise<IntegrationInstance> {
        const response = await api.post(`/api/v1/integrations/instances/${id}/sync`)
        return response.data
    },

    // --- Registry ---
    async listRegistry(): Promise<MCPRegistryItem[]> {
        const response = await api.get('/api/v1/tools/registry')
        return response.data
    },
}

export default integrationService
