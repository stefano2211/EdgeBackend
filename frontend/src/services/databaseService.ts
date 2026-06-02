import api from './api'

export interface SupportedDbType {
    slug: string
    name: string
    default_port: number
    icon_hint: string
}

export interface DatabaseConnection {
    id: string
    name: string
    db_type: string
    host: string
    port: number
    database_name: string
    schema_name: string | null
    is_readonly: boolean
    max_rows: number
    query_timeout: number
    available_in_chat: boolean
    available_in_reactive: boolean
    discovered_schema: any
    last_schema_sync: string | null
    status: string
    status_message: string | null
    created_at: string
    updated_at: string
}

export interface CreateConnectionRequest {
    name: string
    db_type: string
    host: string
    port: number
    database_name: string
    username: string
    password: string
    schema_name?: string
    is_readonly?: boolean
    max_rows?: number
    query_timeout?: number
    available_in_chat?: boolean
    available_in_reactive?: boolean
}

export interface UpdateConnectionRequest {
    name?: string
    host?: string
    port?: number
    database_name?: string
    schema_name?: string | null
    is_readonly?: boolean
    max_rows?: number
    query_timeout?: number
    available_in_chat?: boolean
    available_in_reactive?: boolean
}

export interface SchemaDiscoveryResult {
    tables: SchemaTable[]
}

export interface SchemaTable {
    name: string
    description: string | null
    row_count: number | null
    columns: SchemaColumn[]
}

export interface SchemaColumn {
    name: string
    type: string
    nullable: boolean
    is_pk: boolean
    fk_ref: string | null
    description: string | null
}

export interface QueryRequest {
    sql: string
}

export interface QueryResult {
    columns: string[]
    rows: any[][]
    row_count: number
    truncated: boolean
    execution_time_ms: number
}

export const databaseService = {
    getSupportedTypes(): Promise<SupportedDbType[]> {
        return api.get('/api/v1/database/supported-types').then(r => r.data)
    },

    listConnections(context?: string): Promise<DatabaseConnection[]> {
        return api.get('/api/v1/database/connections', { params: context ? { context } : undefined }).then(r => r.data)
    },

    createConnection(data: CreateConnectionRequest): Promise<DatabaseConnection> {
        return api.post('/api/v1/database/connections', data).then(r => r.data)
    },

    getConnection(id: string): Promise<DatabaseConnection> {
        return api.get(`/api/v1/database/connections/${id}`).then(r => r.data)
    },

    updateConnection(id: string, data: UpdateConnectionRequest): Promise<DatabaseConnection> {
        return api.patch(`/api/v1/database/connections/${id}`, data).then(r => r.data)
    },

    deleteConnection(id: string): Promise<void> {
        return api.delete(`/api/v1/database/connections/${id}`)
    },

    testConnection(id: string): Promise<DatabaseConnection> {
        return api.post(`/api/v1/database/connections/${id}/test`).then(r => r.data)
    },

    discoverSchema(id: string): Promise<SchemaDiscoveryResult> {
        return api.post(`/api/v1/database/connections/${id}/discover-schema`).then(r => r.data)
    },

    getSchema(id: string): Promise<SchemaDiscoveryResult> {
        return api.get(`/api/v1/database/connections/${id}/schema`).then(r => r.data)
    },

    enrichSchema(id: string, data: SchemaDiscoveryResult): Promise<SchemaDiscoveryResult> {
        return api.patch(`/api/v1/database/connections/${id}/schema/enrich`, data).then(r => r.data)
    },

    executeQuery(id: string, sql: string): Promise<QueryResult> {
        return api.post(`/api/v1/database/connections/${id}/query`, { sql }).then(r => r.data)
    },
}

export default databaseService
