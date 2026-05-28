import api from './api'

export interface MCPSource {
    id: string
    name: string
    description?: string
    url: string
    type: string
    is_enabled: boolean
    created_at: string
}

export interface ToolConfig {
    id: number
    name: string
    description: string
    is_enabled: boolean
    config: any
    source_id?: string
}

export interface ToolConfigUpdate {
    name?: string
    description?: string
    is_enabled?: boolean
    config?: any
}

const toolService = {
    async listTools(): Promise<ToolConfig[]> {
        const response = await api.get('/api/v1/tools')
        return response.data
    },

    async getTool(id: number): Promise<ToolConfig> {
        const response = await api.get(`/api/v1/tools/${id}`)
        return response.data
    },

    async createTool(tool: Partial<ToolConfig>): Promise<ToolConfig> {
        const response = await api.post('/api/v1/tools', tool)
        return response.data
    },

    async updateTool(id: number, tool: ToolConfigUpdate): Promise<ToolConfig> {
        const response = await api.patch(`/api/v1/tools/${id}`, tool)
        return response.data
    },

    async deleteTool(id: number): Promise<void> {
        await api.delete(`/api/v1/tools/${id}`)
    },

    // MCP Sources
    async listSources(): Promise<MCPSource[]> {
        const response = await api.get('/api/v1/tools/sources/')
        return response.data
    },

    async createSource(source: Partial<MCPSource>): Promise<MCPSource> {
        const response = await api.post('/api/v1/tools/sources/', source)
        return response.data
    },

    async updateSource(id: string, source: Partial<MCPSource>): Promise<MCPSource> {
        const response = await api.patch(`/api/v1/tools/sources/${id}`, source)
        return response.data
    },

    async deleteSource(id: string): Promise<void> {
        await api.delete(`/api/v1/tools/sources/${id}`)
    },

}

export default toolService
