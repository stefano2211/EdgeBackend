<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import toolService, { type ToolConfig, type MCPSource } from '@/services/toolService'

// State
const sources = ref<MCPSource[]>([])
const tools = ref<ToolConfig[]>([])
const selectedSource = ref<MCPSource | null>(null)
const isViewingDetail = ref(false)

const isLoading = ref(true)

// Form State
const isAddingSource = ref(false)
const newSource = ref({
  name: '',
  url: '',
  type: 'rest',
  description: ''
})

// Methods
async function loadData() {
  isLoading.value = true
  try {
    const [sourcesRes, toolsRes] = await Promise.all([
      toolService.listSources(),
      toolService.listTools()
    ])
    sources.value = sourcesRes
    tools.value = toolsRes
  } catch (e) {
    console.error('Failed to load tools/sources', e)
  } finally {
    isLoading.value = false
  }
}

function selectSource(source: MCPSource) {
  selectedSource.value = source
  isViewingDetail.value = true
}

function goBack() {
  isViewingDetail.value = false
  selectedSource.value = null
}

const sourceTools = computed(() => {
  if (!selectedSource.value) return []
  return tools.value.filter(t => t.source_id === selectedSource.value?.id)
})

async function createSource() {
  try {
    const created = await toolService.createSource(newSource.value)
    sources.value.push(created)
    isAddingSource.value = false
    newSource.value = { name: '', url: '', type: 'rest', description: '' }
    selectSource(created)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Failed to create source')
  }
}

async function deleteSource(id: string) {
  if (!confirm('¿Estás seguro de eliminar esta fuente? Se eliminarán todas sus herramientas.')) return
  try {
    await toolService.deleteSource(id)
    sources.value = sources.value.filter(s => s.id !== id)
    if (selectedSource.value?.id === id) goBack()
  } catch (e) {
    console.error('Failed to delete source', e)
  }
}

async function deleteTool(id: number) {
  if (!confirm('Are you sure you want to delete this tool?')) return
  try {
    await toolService.deleteTool(id)
    tools.value = tools.value.filter(t => t.id !== id)
  } catch (e) {
    console.error('Failed to delete tool', e)
  }
}

onMounted(loadData)
</script>

<template>
  <div class="px-6 py-6 max-w-6xl mx-auto space-y-8 h-full overflow-y-auto custom-scrollbar">
    
    <!-- LEVEL 1: MCPSource List -->
    <template v-if="!isViewingDetail">
      <div class="flex items-center justify-between mb-8">
        <div>
          <h2 class="text-2xl font-bold text-white tracking-tight">Fuentes MCP</h2>
          <p class="text-[#7a7a7a] text-sm mt-1">Gestiona APIs industriales y sus conjuntos de herramientas.</p>
        </div>
        <button 
          @click="isAddingSource = !isAddingSource"
          class="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-xl transition-all flex items-center gap-2 shadow-lg shadow-violet-600/20"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
          Añadir fuente
        </button>
      </div>

      <!-- Add Source Form -->
      <transition 
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="transform -translate-y-4 opacity-0"
        enter-to-class="transform translate-y-0 opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="transform translate-y-0 opacity-100"
        leave-to-class="transform -translate-y-4 opacity-0"
      >
        <div v-if="isAddingSource" class="bg-[#2f2f2f]/30 border border-violet-500/20 rounded-3xl p-6 mb-8 backdrop-blur-sm">
          <h3 class="text-lg font-semibold text-white mb-4">Nueva fuente MCP</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div class="space-y-1.5">
              <label class="text-[12px] font-bold text-[#7a7a7a] uppercase ml-1">Nombre</label>
              <input v-model="newSource.name" type="text" placeholder="ej. PLC Fábrica A" class="w-full bg-[#1a1a1a] border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-violet-500/50 outline-none">
            </div>
            <div class="space-y-1.5">
              <label class="text-[12px] font-bold text-[#7a7a7a] uppercase ml-1">Base URL</label>
              <input v-model="newSource.url" type="text" placeholder="https://api.factory.com/v1" class="w-full bg-[#1a1a1a] border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-violet-500/50 outline-none">
            </div>
            <div class="space-y-1.5 md:col-span-2">
              <label class="text-[12px] font-bold text-[#7a7a7a] uppercase ml-1">Tipo</label>
              <select v-model="newSource.type" class="w-full bg-[#1a1a1a] border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-violet-500/50 outline-none appearance-none">
                <option value="rest">REST API (Auto-Bridge)</option>
                <option value="sse">MCP SSE Server</option>
                <option value="stdio">Local Stdio Server</option>
              </select>
            </div>
          </div>
          <div class="flex justify-end gap-3">
            <button @click="isAddingSource = false" class="px-5 py-2 text-[#7a7a7a] hover:text-white transition-colors">Cancelar</button>
            <button @click="createSource" :disabled="!newSource.name || !newSource.url" class="px-6 py-2 bg-white text-black font-bold rounded-xl hover:bg-white/90 disabled:opacity-50 transition-all">Crear fuente</button>
          </div>
        </div>
      </transition>

      <!-- Sources Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div v-if="isLoading" class="col-span-full py-20 text-center">
          <svg class="animate-spin w-8 h-8 text-violet-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <p class="text-[#7a7a7a]">Cargando fuentes...</p>
        </div>

        <div 
          v-for="source in sources" 
          :key="source.id"
          @click="selectSource(source)"
          class="group relative bg-[#2f2f2f]/30 border border-white/[0.06] rounded-3xl p-6 hover:border-violet-500/30 hover:bg-[#2f2f2f]/50 transition-all cursor-pointer overflow-hidden backdrop-blur-sm"
        >
          <!-- Background Decoration -->
          <div class="absolute -right-4 -top-4 w-24 h-24 bg-violet-600/5 rounded-full blur-3xl group-hover:bg-violet-600/10 transition-all"></div>
          
          <div class="flex flex-col h-full">
            <div class="flex items-start justify-between mb-4">
              <div class="w-12 h-12 rounded-2xl bg-violet-500/10 flex items-center justify-center border border-violet-500/20 text-violet-400 group-hover:scale-110 transition-transform duration-300">
                <svg v-if="source.type === 'rest'" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
              </div>
              <button @click.stop="deleteSource(source.id)" class="opacity-0 group-hover:opacity-100 p-2 text-[#4a4a4a] hover:text-red-400 transition-all">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
              </button>
            </div>
            
            <h3 class="text-lg font-semibold text-white mb-1 group-hover:text-violet-400 transition-colors">{{ source.name }}</h3>
            <p class="text-[13px] text-[#7a7a7a] line-clamp-1 mb-4">{{ source.url }}</p>
            
            <div class="mt-auto flex items-center justify-between">
              <span class="text-[11px] font-bold uppercase tracking-widest text-[#4a4a4a]">{{ source.type }}</span>
              <div class="flex items-center gap-1.5 text-violet-400">
                <span class="text-sm font-medium">{{ tools.filter(t => t.source_id === source.id).length }} tools</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="!isLoading && sources.length === 0" class="col-span-full py-20 bg-white/[0.02] border border-dashed border-white/10 rounded-3xl text-center">
          <p class="text-[#7a7a7a] mb-4">No hay fuentes definidas aún.</p>
          <button @click="isAddingSource = true" class="text-violet-400 font-medium hover:text-violet-300 transition-colors">Crea tu primera fuente MCP →</button>
        </div>
      </div>
    </template>

    <!-- LEVEL 2: MCPSource Detail -->
    <template v-else-if="selectedSource">
      <!-- Detail Header -->
      <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-4">
          <button @click="goBack" class="p-2.5 bg-[#2f2f2f]/50 border border-white/10 rounded-xl text-white hover:bg-[#3f3f3f] transition-all">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
          </button>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-2xl font-bold text-white">{{ selectedSource.name }}</h2>
              <span class="px-2 py-0.5 bg-violet-500/10 text-violet-400 text-[10px] font-bold uppercase rounded border border-violet-500/20">{{ selectedSource.type }}</span>
            </div>
            <p class="text-[#7a7a7a] text-sm font-mono mt-0.5">{{ selectedSource.url }}</p>
          </div>
        </div>
        <button 
          @click="deleteSource(selectedSource!.id)"
          class="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 rounded-xl transition-all"
          title="Eliminar fuente"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
        </button>
      </div>

      <div class="max-w-3xl mx-auto space-y-8">
          
          <!-- Current Registered Tools -->
          <section>
            <h3 class="text-[#7a7a7a] text-[11px] font-bold uppercase tracking-widest mb-5 ml-1">Herramientas configuradas ({{ sourceTools.length }})</h3>
            <div class="grid grid-cols-1 gap-4">
              <div 
                v-for="tool in sourceTools" 
                :key="tool.id"
                class="bg-[#2f2f2f]/30 border border-white/5 rounded-2xl p-4 flex items-center justify-between group hover:border-white/10 transition-all"
              >
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform duration-300">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a2 2 0 0 1-2.83-2.83l-3.94 3.94Z"/><path d="m.74 23.26 3.13-3.13a2 2 0 1 1 2.83 2.83L1.58 26.09a2 2 0 0 1-2.83-2.83Z"/><path d="m3.13 1.58 4.58 4.58c.77.77.77 2.03 0 2.8a2 2 0 0 1-2.8 0L.33 4.38a2 2 0 0 1 2.8-2.8Z"/><path d="m17.58 17.58 4.58 4.58a2.02 2.02 0 1 1-2.83 2.83l-4.58-4.58a2 2 0 0 1 2.83-2.83Z"/></svg>
                  </div>
                  <div>
                    <h4 class="text-white font-medium text-sm">{{ tool.name }}</h4>
                    <p class="text-[#4a4a4a] text-[12px] line-clamp-1 italic">{{ tool.description }}</p>
                  </div>
                </div>
                <button @click="deleteTool(tool.id)" class="p-2 text-[#3a3a3a] hover:text-red-400 transition-colors">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                </button>
              </div>
              <div v-if="sourceTools.length === 0" class="text-center py-10 bg-white/[0.01] border border-dashed border-white/5 rounded-2xl">
                <p class="text-[#4a4a4a] text-sm">No hay herramientas registradas para esta fuente aún.</p>
              </div>
            </div>
          </section>

          <!-- Search Results -->
      </div>
    </template>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.1); }
</style>
