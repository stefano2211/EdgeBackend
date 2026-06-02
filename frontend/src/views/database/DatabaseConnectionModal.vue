<script setup lang="ts">
import { ref, watch } from 'vue'
import databaseService, { type DatabaseConnection, type CreateConnectionRequest } from '@/services/databaseService'

const props = defineProps<{
    connection: DatabaseConnection | null
}>()

const emit = defineEmits<{
    (e: 'close'): void
    (e: 'saved'): void
}>()

const form = ref<CreateConnectionRequest>({
    name: '',
    db_type: 'postgresql',
    host: '',
    port: 5432,
    database_name: '',
    username: '',
    password: '',
    is_readonly: true,
    max_rows: 1000,
    query_timeout: 30,
    available_in_chat: true,
    available_in_reactive: false,
})

const testing = ref(false)
const testResult = ref<string | null>(null)
const saving = ref(false)

watch(() => props.connection, (conn) => {
    if (conn) {
        form.value = {
            name: conn.name,
            db_type: conn.db_type,
            host: conn.host,
            port: conn.port,
            database_name: conn.database_name,
            username: '',
            password: '',
            schema_name: conn.schema_name || undefined,
            is_readonly: conn.is_readonly,
            max_rows: conn.max_rows,
            query_timeout: conn.query_timeout,
            available_in_chat: conn.available_in_chat,
            available_in_reactive: conn.available_in_reactive,
        }
    }
}, { immediate: true })

watch(() => form.value.db_type, (type) => {
    if (type === 'postgresql') form.value.port = 5432
    else if (type === 'mysql') form.value.port = 3306
})

async function handleTest() {
    testing.value = true
    testResult.value = null
    try {
        // Create temporarily to test
        const created = await databaseService.createConnection(form.value)
        const result = await databaseService.testConnection(created.id)
        testResult.value = result.status === 'connected' ? 'Conexion exitosa!' : `Error: ${result.status_message}`
        // Delete the temp if we are in create mode
        if (!props.connection) {
            await databaseService.deleteConnection(created.id)
        }
    } catch (e: any) {
        testResult.value = `Error: ${e.response?.data?.detail || e.message}`
    } finally {
        testing.value = false
    }
}

async function handleSave() {
    saving.value = true
    try {
        if (props.connection) {
            await databaseService.updateConnection(props.connection.id, {
                name: form.value.name,
                host: form.value.host,
                port: form.value.port,
                database_name: form.value.database_name,
                schema_name: form.value.schema_name,
                is_readonly: form.value.is_readonly,
                max_rows: form.value.max_rows,
                query_timeout: form.value.query_timeout,
                available_in_chat: form.value.available_in_chat,
                available_in_reactive: form.value.available_in_reactive,
            })
        } else {
            await databaseService.createConnection(form.value)
        }
        emit('saved')
    } catch (e: any) {
        alert(`Error: ${e.response?.data?.detail || e.message}`)
    } finally {
        saving.value = false
    }
}
</script>

<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div class="bg-[#141414] border border-white/[0.06] rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-lg font-semibold text-white">
                    {{ props.connection ? 'Editar Conexion' : 'Nueva Conexion' }}
                </h2>
                <button @click="$emit('close')" class="text-[#7a7a7a] hover:text-white">&times;</button>
            </div>

            <div class="space-y-4">
                <!-- DB Type -->
                <div>
                    <label class="block text-sm text-[#b4b4b4] mb-1">Tipo de Base de Datos</label>
                    <div class="flex gap-2">
                        <button
                            v-for="t in [{slug:'postgresql',name:'PostgreSQL'},{slug:'mysql',name:'MySQL'}]"
                            :key="t.slug"
                            @click="form.db_type = t.slug"
                            class="flex-1 px-4 py-2 text-sm rounded-lg border transition-colors"
                            :class="form.db_type === t.slug ? 'border-cyan-400 text-cyan-400 bg-cyan-400/10' : 'border-white/[0.06] text-[#b4b4b4] hover:border-white/20'"
                        >
                            {{ t.name }}
                        </button>
                    </div>
                </div>

                <!-- Name -->
                <div>
                    <label class="block text-sm text-[#b4b4b4] mb-1">Nombre</label>
                    <input v-model="form.name" class="w-full px-3 py-2 bg-[#0a0a0a] border border-white/[0.06] rounded-lg text-white text-sm focus:border-cyan-400 focus:outline-none" />
                </div>

                <!-- Host + Port -->
                <div class="flex gap-3">
                    <div class="flex-1">
                        <label class="block text-sm text-[#b4b4b4] mb-1">Host</label>
                        <input v-model="form.host" class="w-full px-3 py-2 bg-[#0a0a0a] border border-white/[0.06] rounded-lg text-white text-sm focus:border-cyan-400 focus:outline-none" />
                    </div>
                    <div class="w-24">
                        <label class="block text-sm text-[#b4b4b4] mb-1">Puerto</label>
                        <input v-model.number="form.port" type="number" class="w-full px-3 py-2 bg-[#0a0a0a] border border-white/[0.06] rounded-lg text-white text-sm focus:border-cyan-400 focus:outline-none" />
                    </div>
                </div>

                <!-- Database -->
                <div>
                    <label class="block text-sm text-[#b4b4b4] mb-1">Base de Datos</label>
                    <input v-model="form.database_name" class="w-full px-3 py-2 bg-[#0a0a0a] border border-white/[0.06] rounded-lg text-white text-sm focus:border-cyan-400 focus:outline-none" />
                </div>

                <!-- Schema (PG only) -->
                <div v-if="form.db_type === 'postgresql'">
                    <label class="block text-sm text-[#b4b4b4] mb-1">Schema (opcional)</label>
                    <input v-model="form.schema_name" placeholder="public" class="w-full px-3 py-2 bg-[#0a0a0a] border border-white/[0.06] rounded-lg text-white text-sm focus:border-cyan-400 focus:outline-none" />
                </div>

                <!-- Credentials -->
                <div class="flex gap-3">
                    <div class="flex-1">
                        <label class="block text-sm text-[#b4b4b4] mb-1">Usuario</label>
                        <input v-model="form.username" class="w-full px-3 py-2 bg-[#0a0a0a] border border-white/[0.06] rounded-lg text-white text-sm focus:border-cyan-400 focus:outline-none" />
                    </div>
                    <div class="flex-1">
                        <label class="block text-sm text-[#b4b4b4] mb-1">Password</label>
                        <input v-model="form.password" type="password" class="w-full px-3 py-2 bg-[#0a0a0a] border border-white/[0.06] rounded-lg text-white text-sm focus:border-cyan-400 focus:outline-none" />
                    </div>
                </div>

                <!-- Options -->
                <div class="bg-[#0a0a0a] border border-white/[0.06] rounded-lg p-4 space-y-3">
                    <h4 class="text-sm font-medium text-white">Opciones</h4>

                    <label class="flex items-center gap-2 cursor-pointer">
                        <input v-model="form.is_readonly" type="checkbox" class="accent-cyan-400" />
                        <span class="text-sm text-[#b4b4b4]">Solo lectura</span>
                    </label>

                    <label class="flex items-center gap-2 cursor-pointer">
                        <input v-model="form.available_in_chat" type="checkbox" class="accent-cyan-400" />
                        <span class="text-sm text-[#b4b4b4]">Disponible en Chat</span>
                    </label>

                    <label class="flex items-center gap-2 cursor-pointer">
                        <input v-model="form.available_in_reactive" type="checkbox" class="accent-cyan-400" />
                        <span class="text-sm text-[#b4b4b4]">Disponible en Reactiva</span>
                    </label>

                    <div class="flex gap-3">
                        <div class="flex-1">
                            <label class="block text-xs text-[#7a7a7a] mb-1">Max filas</label>
                            <input v-model.number="form.max_rows" type="number" class="w-full px-2 py-1 bg-[#141414] border border-white/[0.06] rounded text-white text-sm" />
                        </div>
                        <div class="flex-1">
                            <label class="block text-xs text-[#7a7a7a] mb-1">Timeout (s)</label>
                            <input v-model.number="form.query_timeout" type="number" class="w-full px-2 py-1 bg-[#141414] border border-white/[0.06] rounded text-white text-sm" />
                        </div>
                    </div>
                </div>

                <!-- Test result -->
                <div v-if="testResult" class="text-sm" :class="testResult.includes('exitosa') ? 'text-emerald-400' : 'text-red-400'">
                    {{ testResult }}
                </div>
            </div>

            <div class="flex items-center justify-end gap-2 mt-6">
                <button
                    @click="handleTest"
                    :disabled="testing"
                    class="px-4 py-2 text-sm font-medium text-cyan-400 bg-cyan-400/10 rounded-lg hover:bg-cyan-400/20 transition-colors disabled:opacity-50"
                >
                    {{ testing ? 'Probando...' : 'Probar' }}
                </button>
                <button
                    @click="handleSave"
                    :disabled="saving"
                    class="px-4 py-2 text-sm font-medium text-black bg-cyan-400 rounded-lg hover:bg-cyan-300 transition-colors disabled:opacity-50"
                >
                    {{ saving ? 'Guardando...' : 'Guardar' }}
                </button>
            </div>
        </div>
    </div>
</template>
