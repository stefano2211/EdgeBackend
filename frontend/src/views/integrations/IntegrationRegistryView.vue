<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import integrationService, { type MCPRegistryItem } from '@/services/integrationService'

const registry = ref<MCPRegistryItem[]>([])
const isLoading = ref(true)
const searchQuery = ref('')
const contextFilter = ref('all')
const transportFilter = ref('all')

const contexts = [
  { value: 'all', label: 'Todos' },
  { value: 'chat', label: 'Chat' },
  { value: 'reactive', label: 'Reactive' },
  { value: 'both', label: 'Both' },
]

const transports = [
  { value: 'all', label: 'Todos' },
  { value: 'stdio', label: 'Stdio' },
  { value: 'rest', label: 'REST' },
  { value: 'sse', label: 'SSE' },
]

const filteredRegistry = computed(() => {
  return registry.value.filter(item => {
    const matchesSearch = !searchQuery.value ||
      item.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      item.source_name.toLowerCase().includes(searchQuery.value.toLowerCase())
    const matchesContext = contextFilter.value === 'all' || item.context === contextFilter.value
    const matchesTransport = transportFilter.value === 'all' || item.transport === transportFilter.value
    return matchesSearch && matchesContext && matchesTransport
  })
})

const groupedBySource = computed(() => {
  const groups: Record<string, MCPRegistryItem[]> = {}
  for (const item of filteredRegistry.value) {
    const key = item.source_name
    if (!groups[key]) groups[key] = []
    groups[key].push(item)
  }
  return groups
})

const stats = computed(() => {
  const total = registry.value.length
  const chat = registry.value.filter(i => i.context === 'chat' || i.context === 'both').length
  const reactive = registry.value.filter(i => i.context === 'reactive' || i.context === 'both').length
  const official = registry.value.filter(i => i.source_type === 'official').length
  const custom = registry.value.filter(i => i.source_type === 'custom').length
    return { total, chat, reactive, official, custom }
})

async function loadData() {
  isLoading.value = true
  try {
    registry.value = await integrationService.listRegistry()
  } catch (e) {
    console.error('Failed to load registry', e)
  } finally {
    isLoading.value = false
  }
}

function getContextBadge(context: string) {
  switch (context) {
    case 'chat': return { label: 'Chat', class: 'bg-violet-500/10 text-violet-400 border-violet-500/20' }
    case 'reactive': return { label: 'Reactive', class: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' }
    case 'both': return { label: 'Both', class: 'bg-blue-500/10 text-blue-400 border-blue-500/20' }
    default: return { label: context, class: 'bg-[#1a1a1a] text-[#4a4a4a] border-white/5' }
  }
}

function getTransportBadge(transport: string) {
  switch (transport) {
    case 'stdio': return { label: 'Stdio', class: 'bg-amber-500/10 text-amber-400 border-amber-500/20' }
    case 'rest': return { label: 'REST', class: 'bg-sky-500/10 text-sky-400 border-sky-500/20' }
    case 'sse': return { label: 'SSE', class: 'bg-pink-500/10 text-pink-400 border-pink-500/20' }
    default: return { label: transport, class: 'bg-[#1a1a1a] text-[#4a4a4a] border-white/5' }
  }
}

function getSourceTypeBadge(sourceType: string) {
  switch (sourceType) {
    case 'official': return { label: 'Oficial', class: 'bg-blue-500/10 text-blue-400 border-blue-500/20' }
    case 'custom': return { label: 'Custom', class: 'bg-amber-500/10 text-amber-400 border-amber-500/20' }
    default: return { label: sourceType, class: 'bg-[#1a1a1a] text-[#4a4a4a] border-white/5' }
  }
}

onMounted(loadData)
</script>

<template>
  <div class="px-6 py-6 max-w-6xl mx-auto space-y-6 h-full overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-2xl font-bold text-white tracking-tight">Registry</h2>
        <p class="text-[#7a7a7a] text-sm mt-1">Todos los MCP tools activos en el sistema.</p>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <div class="bg-[#2f2f2f]/30 border border-white/[0.06] rounded-xl p-3 text-center">
        <div class="text-lg font-bold text-white">{{ stats.total }}</div>
        <div class="text-[10px] text-[#7a7a7a] uppercase tracking-wider">Total</div>
      </div>
      <div class="bg-[#2f2f2f]/30 border border-violet-500/10 rounded-xl p-3 text-center">
        <div class="text-lg font-bold text-violet-400">{{ stats.chat }}</div>
        <div class="text-[10px] text-[#7a7a7a] uppercase tracking-wider">Chat</div>
      </div>
      <div class="bg-[#2f2f2f]/30 border border-emerald-500/10 rounded-xl p-3 text-center">
        <div class="text-lg font-bold text-emerald-400">{{ stats.reactive }}</div>
        <div class="text-[10px] text-[#7a7a7a] uppercase tracking-wider">Reactive</div>
      </div>
      <div class="bg-[#2f2f2f]/30 border border-blue-500/10 rounded-xl p-3 text-center">
        <div class="text-lg font-bold text-blue-400">{{ stats.official }}</div>
        <div class="text-[10px] text-[#7a7a7a] uppercase tracking-wider">Oficiales</div>
      </div>
      <div class="bg-[#2f2f2f]/30 border border-amber-500/10 rounded-xl p-3 text-center">
        <div class="text-lg font-bold text-amber-400">{{ stats.custom }}</div>
        <div class="text-[10px] text-[#7a7a7a] uppercase tracking-wider">Custom</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-col md:flex-row gap-3">
      <div class="relative flex-1">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#4a4a4a]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar tool o source..."
          class="w-full bg-[#1a1a1a] border border-white/10 rounded-xl pl-9 pr-4 py-2 text-[13px] text-white placeholder-[#4a4a4a] focus:border-violet-500/50 outline-none"
        >
      </div>
      <div class="flex gap-2">
        <select v-model="contextFilter" class="bg-[#1a1a1a] border border-white/10 rounded-xl px-3 py-2 text-[13px] text-white focus:border-violet-500/50 outline-none appearance-none">
          <option v-for="ctx in contexts" :key="ctx.value" :value="ctx.value">{{ ctx.label }}</option>
        </select>
        <select v-model="transportFilter" class="bg-[#1a1a1a] border border-white/10 rounded-xl px-3 py-2 text-[13px] text-white focus:border-violet-500/50 outline-none appearance-none">
          <option v-for="t in transports" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="py-20 text-center">
      <svg class="animate-spin w-8 h-8 text-violet-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
      <p class="text-[#7a7a7a]">Cargando registry...</p>
    </div>

    <!-- Empty -->
    <div v-else-if="filteredRegistry.length === 0" class="py-16 bg-white/[0.02] border border-dashed border-white/10 rounded-2xl text-center">
      <p class="text-[#7a7a7a]">No hay MCP tools que coincidan con los filtros.</p>
    </div>

    <!-- Registry Table -->
    <div v-else class="space-y-4">
      <div
        v-for="(tools, sourceName) in groupedBySource"
        :key="sourceName"
        class="bg-[#2f2f2f]/30 border border-white/[0.06] rounded-2xl overflow-hidden"
      >
        <!-- Source Header -->
        <div class="px-5 py-3 border-b border-white/[0.06] flex items-center gap-3">
          <div class="w-2 h-2 rounded-full" :class="tools[0].source_type === 'official' ? 'bg-blue-400' : tools[0].source_type === 'custom' ? 'bg-amber-400' : 'bg-emerald-400'"></div>
          <span class="text-[13px] font-semibold text-white">{{ sourceName }}</span>
          <span class="text-[10px] px-2 py-0.5 rounded border" :class="getSourceTypeBadge(tools[0].source_type).class">
            {{ getSourceTypeBadge(tools[0].source_type).label }}
          </span>
          <span class="text-[11px] text-[#4a4a4a] ml-auto">{{ tools.length }} tool{{ tools.length > 1 ? 's' : '' }}</span>
        </div>

        <!-- Tools List -->
        <div class="divide-y divide-white/[0.04]">
          <div
            v-for="tool in tools"
            :key="tool.id"
            class="px-5 py-3 flex items-center gap-4 hover:bg-white/[0.02] transition-colors"
          >
            <div class="w-2 h-2 rounded-full shrink-0" :class="tool.is_enabled ? 'bg-emerald-400' : 'bg-[#4a4a4a]'"></div>

            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-[13px] font-medium text-white">{{ tool.name }}</span>
                <span v-if="tool.instance_name" class="text-[10px] text-[#4a4a4a]">({{ tool.instance_name }})</span>
              </div>
              <p v-if="tool.description" class="text-[11px] text-[#7a7a7a] truncate">{{ tool.description }}</p>
            </div>

            <div class="flex items-center gap-2 shrink-0">
              <span class="text-[10px] px-2 py-0.5 rounded border" :class="getContextBadge(tool.context).class">
                {{ getContextBadge(tool.context).label }}
              </span>
              <span class="text-[10px] px-2 py-0.5 rounded border" :class="getTransportBadge(tool.transport).class">
                {{ getTransportBadge(tool.transport).label }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.1); }
</style>
