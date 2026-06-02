<script setup lang="ts">
import { ref, onMounted } from 'vue'
import databaseService, { type SchemaDiscoveryResult, type SchemaTable } from '@/services/databaseService'

const props = defineProps<{
    connectionId: string
}>()

const schema = ref<SchemaDiscoveryResult | null>(null)
const loading = ref(false)
const expandedTables = ref<Set<string>>(new Set())

async function loadSchema() {
    loading.value = true
    try {
        schema.value = await databaseService.getSchema(props.connectionId)
    } finally {
        loading.value = false
    }
}

function toggleTable(name: string) {
    if (expandedTables.value.has(name)) {
        expandedTables.value.delete(name)
    } else {
        expandedTables.value.add(name)
    }
}

function getColumnIcon(type: string): string {
    const t = type.toLowerCase()
    if (t.includes('int')) return '#'
    if (t.includes('char') || t.includes('text')) return 'T'
    if (t.includes('date') || t.includes('time')) return '📅'
    if (t.includes('bool')) return '✓'
    if (t.includes('json')) return '{}'
    if (t.includes('uuid')) return '🔑'
    return '?'
}

onMounted(loadSchema)
</script>

<template>
    <div class="p-4 h-full overflow-auto">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-medium text-white">Schema</h3>
            <button
                @click="loadSchema"
                :disabled="loading"
                class="text-xs px-2 py-1 bg-cyan-400/10 text-cyan-400 rounded hover:bg-cyan-400/20"
            >
                {{ loading ? '...' : 'Refrescar' }}
            </button>
        </div>

        <div v-if="!schema || schema.tables.length === 0" class="text-sm text-[#7a7a7a]">
            No schema discovered yet.
        </div>

        <div v-else class="space-y-1">
            <div
                v-for="table in schema.tables"
                :key="table.name"
                class="border border-white/[0.06] rounded-lg overflow-hidden"
            >
                <button
                    @click="toggleTable(table.name)"
                    class="w-full flex items-center justify-between px-3 py-2 bg-[#141414] hover:bg-[#1a1a1a] transition-colors"
                >
                    <div class="flex items-center gap-2">
                        <span class="text-[#7a7a7a]">📋</span>
                        <span class="text-sm text-white">{{ table.name }}</span>
                        <span v-if="table.row_count !== null" class="text-xs text-[#7a7a7a]">
                            ({{ table.row_count.toLocaleString() }} filas)
                        </span>
                    </div>
                    <span class="text-xs text-[#7a7a7a]">
                        {{ expandedTables.has(table.name) ? '▼' : '▶' }}
                    </span>
                </button>

                <div v-if="expandedTables.has(table.name)" class="px-3 py-2 space-y-1">
                    <div
                        v-for="col in table.columns"
                        :key="col.name"
                        class="flex items-center gap-2 text-xs"
                    >
                        <span class="text-[#7a7a7a] w-4 text-center">{{ getColumnIcon(col.type) }}</span>
                        <span class="text-[#b4b4b4]">{{ col.name }}</span>
                        <span class="text-[#7a7a7a]">{{ col.type }}</span>
                        <span v-if="col.is_pk" class="px-1 py-0.5 bg-cyan-400/20 text-cyan-400 rounded text-[10px]">PK</span>
                        <span v-if="!col.nullable" class="px-1 py-0.5 bg-red-400/20 text-red-400 rounded text-[10px]">NOT NULL</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
