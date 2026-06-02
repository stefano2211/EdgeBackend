<script setup lang="ts">
import { ref, onMounted } from 'vue'
import databaseService, { type DatabaseConnection } from '@/services/databaseService'
import DatabaseConnectionModal from '@/views/database/DatabaseConnectionModal.vue'

const connections = ref<DatabaseConnection[]>([])
const loading = ref(false)
const showModal = ref(false)
const selectedConnection = ref<DatabaseConnection | null>(null)

async function loadConnections() {
    loading.value = true
    try {
        connections.value = await databaseService.listConnections()
    } finally {
        loading.value = false
    }
}

async function toggleChat(conn: DatabaseConnection) {
    const newValue = !conn.available_in_chat
    try {
        await databaseService.updateConnection(conn.id, {
            available_in_chat: newValue,
        })
        conn.available_in_chat = newValue
    } catch (e) {
        alert('Failed to update')
    }
}

async function toggleReactive(conn: DatabaseConnection) {
    const newValue = !conn.available_in_reactive
    try {
        await databaseService.updateConnection(conn.id, {
            available_in_reactive: newValue,
        })
        conn.available_in_reactive = newValue
    } catch (e) {
        alert('Failed to update')
    }
}

async function testConnection(conn: DatabaseConnection) {
    conn.status = 'disconnected'
    conn.status_message = 'Testing...'
    try {
        const updated = await databaseService.testConnection(conn.id)
        const idx = connections.value.findIndex(c => c.id === conn.id)
        if (idx !== -1) {
            connections.value[idx] = { ...connections.value[idx], ...updated }
        }
    } catch (e) {
        conn.status = 'error'
        conn.status_message = 'Test failed'
    }
}

async function discoverSchema(conn: DatabaseConnection) {
    try {
        await databaseService.discoverSchema(conn.id)
        const updated = await databaseService.getConnection(conn.id)
        const idx = connections.value.findIndex(c => c.id === conn.id)
        if (idx !== -1) {
            connections.value[idx] = updated
        }
    } catch (e) {
        alert('Schema discovery failed')
    }
}

async function deleteConnection(conn: DatabaseConnection) {
    if (!confirm(`Eliminar conexion "${conn.name}"?`)) return
    try {
        await databaseService.deleteConnection(conn.id)
        connections.value = connections.value.filter(c => c.id !== conn.id)
    } catch (e) {
        alert('Delete failed')
    }
}

function openEdit(conn: DatabaseConnection) {
    selectedConnection.value = conn
    showModal.value = true
}

function openCreate() {
    selectedConnection.value = null
    showModal.value = true
}

function onSaved() {
    showModal.value = false
    selectedConnection.value = null
    loadConnections()
}

function getDbIcon(type: string): string {
    if (type === 'postgresql') return '🐘'
    if (type === 'mysql') return '🐬'
    return '🗄️'
}

function getStatusColor(status: string): string {
    if (status === 'connected') return 'bg-emerald-400'
    if (status === 'error') return 'bg-red-400'
    return 'bg-yellow-400'
}

function getTableCount(conn: DatabaseConnection): number {
    return conn.discovered_schema?.tables?.length || 0
}

onMounted(loadConnections)
</script>

<template>
    <div class="p-6 h-full overflow-auto">
        <div class="flex items-center justify-between mb-6">
            <div>
                <h1 class="text-xl font-semibold text-white">Bases de Datos</h1>
                <p class="text-sm text-[#7a7a7a] mt-1">Gestiona conexiones disponibles para el sistema reactivo</p>
            </div>
            <button
                @click="openCreate"
                class="px-4 py-2 text-sm font-medium text-black bg-cyan-400 rounded-lg hover:bg-cyan-300 transition-colors"
            >
                + Nueva Conexion
            </button>
        </div>

        <div v-if="loading" class="text-[#7a7a7a]">Cargando...</div>

        <div v-else-if="connections.length === 0" class="text-center py-12">
            <div class="text-4xl mb-4">🗄️</div>
            <p class="text-[#b4b4b4] mb-4">No hay conexiones configuradas</p>
            <button
                @click="openCreate"
                class="px-4 py-2 text-sm font-medium text-black bg-cyan-400 rounded-lg hover:bg-cyan-300"
            >
                Conectar primera base de datos
            </button>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
                v-for="conn in connections"
                :key="conn.id"
                class="bg-[#141414] border border-white/[0.06] rounded-xl p-4 hover:border-cyan-400/30 transition-colors"
            >
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="text-2xl">{{ getDbIcon(conn.db_type) }}</span>
                        <div>
                            <h3 class="font-medium text-white">{{ conn.name }}</h3>
                            <p class="text-xs text-[#7a7a7a]">
                                {{ conn.host }}:{{ conn.port }}/{{ conn.database_name }}
                            </p>
                        </div>
                    </div>
                    <span
                        class="w-2.5 h-2.5 rounded-full"
                        :class="getStatusColor(conn.status)"
                        :title="conn.status"
                    />
                </div>

                <!-- Context toggles -->
                <div class="flex items-center gap-3 mb-3">
                    <label class="flex items-center gap-1.5 cursor-pointer text-xs text-[#b4b4b4] hover:text-white transition-colors">
                        <input
                            type="checkbox"
                            :checked="conn.available_in_chat"
                            @change="toggleChat(conn)"
                            class="accent-cyan-400 w-3.5 h-3.5"
                        />
                        Chat
                    </label>
                    <label class="flex items-center gap-1.5 cursor-pointer text-xs text-[#b4b4b4] hover:text-white transition-colors">
                        <input
                            type="checkbox"
                            :checked="conn.available_in_reactive"
                            @change="toggleReactive(conn)"
                            class="accent-violet-400 w-3.5 h-3.5"
                        />
                        <span :class="conn.available_in_reactive ? 'text-violet-400 font-medium' : ''">Reactiva</span>
                    </label>
                    <span class="text-xs text-[#7a7a7a] ml-auto">{{ getTableCount(conn) }} tablas</span>
                </div>

                <!-- Actions -->
                <div class="flex items-center gap-2">
                    <button
                        @click="testConnection(conn)"
                        class="text-xs px-2 py-1 bg-white/[0.06] rounded hover:bg-white/[0.1] text-[#b4b4b4] hover:text-white transition-colors"
                        :disabled="conn.status === 'disconnected' && conn.status_message === 'Testing...'"
                    >
                        {{ conn.status_message === 'Testing...' ? 'Probando...' : 'Test' }}
                    </button>
                    <button
                        @click="discoverSchema(conn)"
                        class="text-xs px-2 py-1 bg-white/[0.06] rounded hover:bg-white/[0.1] text-[#b4b4b4] hover:text-white transition-colors"
                    >
                        Schema
                    </button>
                    <button
                        @click="openEdit(conn)"
                        class="text-xs px-2 py-1 bg-white/[0.06] rounded hover:bg-white/[0.1] text-[#b4b4b4] hover:text-white transition-colors"
                    >
                        Editar
                    </button>
                    <button
                        @click="deleteConnection(conn)"
                        class="text-xs px-2 py-1 bg-red-400/10 text-red-400 rounded hover:bg-red-400/20 transition-colors"
                    >
                        Eliminar
                    </button>
                </div>
            </div>
        </div>

        <DatabaseConnectionModal
            v-if="showModal"
            :connection="selectedConnection"
            @close="showModal = false"
            @saved="onSaved"
        />
    </div>
</template>
