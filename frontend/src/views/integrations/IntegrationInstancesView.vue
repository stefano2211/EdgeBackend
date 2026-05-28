<script setup lang="ts">
import { ref, onMounted, inject } from 'vue'
import integrationService, { type IntegrationInstance } from '@/services/integrationService'

const instances = ref<IntegrationInstance[]>([])
const isLoading = ref(true)
const syncingId = ref<number | null>(null)

const refreshMcpSources = inject<() => Promise<void>>('refreshMcpSources', async () => {})

const CATEGORY_COLORS: Record<string, string> = {
  development: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  communication: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  database: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  cloud: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
  productivity: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
}



async function loadData() {
  isLoading.value = true
  try {
    instances.value = await integrationService.listInstances()
  } catch (e) {
    console.error('Failed to load instances', e)
  } finally {
    isLoading.value = false
  }
}

async function toggleChat(inst: IntegrationInstance) {
  if (syncingId.value !== null) return
  syncingId.value = inst.id
  try {
    await integrationService.updateInstance(inst.id, {
      available_in_chat: !inst.available_in_chat
    })
    inst.available_in_chat = !inst.available_in_chat
    await loadData()
    // Refresh MCP sources in dropdown
    await refreshMcpSources()
  } catch (e) {
    console.error('Failed to toggle chat', e)
  } finally {
    syncingId.value = null
  }
}

async function syncInstance(inst: IntegrationInstance) {
  if (syncingId.value !== null) return
  syncingId.value = inst.id
  try {
    await integrationService.syncInstance(inst.id)
    await loadData()
    await refreshMcpSources()
  } catch (e) {
    console.error('Failed to sync instance', e)
    alert('Error al sincronizar. Revisa que el proceso esté corriendo.')
  } finally {
    syncingId.value = null
  }
}

async function toggleReactive(inst: IntegrationInstance) {
  if (syncingId.value !== null) return
  syncingId.value = inst.id
  try {
    await integrationService.updateInstance(inst.id, {
      available_in_reactive: !inst.available_in_reactive
    })
    inst.available_in_reactive = !inst.available_in_reactive
    await loadData()
    // Refresh MCP sources in dropdown
    await refreshMcpSources()
  } catch (e) {
    console.error('Failed to toggle reactive', e)
  } finally {
    syncingId.value = null
  }
}

async function deleteInstance(inst: IntegrationInstance) {
  if (!confirm(`¿Eliminar "${inst.instance_name}" permanentemente? Se eliminarán credenciales y proceso.`)) return
  try {
    await integrationService.deleteInstance(inst.id)
    instances.value = instances.value.filter(i => i.id !== inst.id)
  } catch (e) {
    console.error('Failed to delete', e)
  }
}



onMounted(loadData)
</script>

<template>
  <div class="px-6 py-6 max-w-6xl mx-auto space-y-8 h-full overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h2 class="text-2xl font-bold text-white tracking-tight">Mis Instancias</h2>
        <p class="text-[#7a7a7a] text-sm mt-1">Gestiona tus integraciones configuradas, activa o desactiva para Chat y Eventos.</p>
      </div>
      <router-link
        to="/integrations/catalog"
        class="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-xl transition-all flex items-center gap-2 shadow-lg shadow-violet-600/20"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
        Nueva Integración
      </router-link>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="py-20 text-center">
      <svg class="animate-spin w-8 h-8 text-violet-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
      <p class="text-[#7a7a7a]">Cargando instancias...</p>
    </div>

    <!-- Empty -->
    <div v-else-if="instances.length === 0" class="py-20 bg-white/[0.02] border border-dashed border-white/10 rounded-3xl text-center">
      <p class="text-[#7a7a7a] mb-4">No tienes integraciones configuradas.</p>
      <router-link to="/integrations/catalog" class="text-violet-400 font-medium hover:text-violet-300 transition-colors">Explorar catálogo &rarr;</router-link>
    </div>

    <!-- Instances Grid -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div
        v-for="inst in instances"
        :key="inst.id"
        class="group relative bg-[#2f2f2f]/30 border border-white/[0.06] rounded-3xl p-6 hover:border-violet-500/30 hover:bg-[#2f2f2f]/50 transition-all overflow-hidden backdrop-blur-sm"
        :class="syncingId === inst.id ? 'opacity-75 pointer-events-none' : ''"
      >
        <div class="absolute -right-4 -top-4 w-24 h-24 bg-violet-600/5 rounded-full blur-3xl group-hover:bg-violet-600/10 transition-all"></div>

        <div class="flex items-start justify-between mb-4">
          <!-- Icon + Name -->
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center border"
              :class="CATEGORY_COLORS[inst.catalog?.category || 'productivity']"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
              </svg>
            </div>
            <div>
              <h3 class="text-lg font-semibold text-white">{{ inst.instance_name }}</h3>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-[12px] text-[#7a7a7a]">{{ inst.catalog?.name }}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded border"
                  :class="inst.catalog?.source_type === 'official' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : 'bg-[#1a1a1a] text-[#4a4a4a] border-white/5'"
                >
                  {{ inst.catalog?.source_type === 'official' ? 'Oficial' : 'Custom' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Syncing Indicator -->
        <div v-if="syncingId === inst.id" class="mb-4 flex items-center gap-2 text-violet-400">
          <svg class="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <span class="text-[12px] font-medium">Aplicando cambios...</span>
        </div>

        <!-- Toggles -->
        <div class="flex items-center gap-6 mb-4">
          <!-- Chat Toggle -->
          <div class="flex items-center gap-3">
            <span class="text-[12px] text-[#7a7a7a]">Chat</span>
            <div
              @click="toggleChat(inst)"
              class="relative w-10 h-5 rounded-full transition-all cursor-pointer border shrink-0"
              :class="inst.available_in_chat ? 'bg-violet-500/20 border-violet-500/40' : 'bg-white/5 border-white/10'"
            >
              <div class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all"
                :class="inst.available_in_chat ? 'left-6 bg-violet-400 shadow-[0_0_8px_rgba(139,92,246,0.5)]' : 'left-1 bg-[#4a4a4a]'"
              ></div>
            </div>
          </div>

          <!-- Reactive Toggle -->
          <div class="flex items-center gap-3">
            <span class="text-[12px] text-[#7a7a7a]">Eventos</span>
            <div
              @click="toggleReactive(inst)"
              class="relative w-10 h-5 rounded-full transition-all cursor-pointer border shrink-0"
              :class="inst.available_in_reactive ? 'bg-emerald-500/20 border-emerald-500/40' : 'bg-white/5 border-white/10'"
            >
              <div class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all"
                :class="inst.available_in_reactive ? 'left-6 bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'left-1 bg-[#4a4a4a]'"
              ></div>
            </div>
          </div>
        </div>

        <!-- Sync warnings -->
        <div v-if="inst.available_in_chat && !inst.mcp_source_id" class="mt-2 flex items-center gap-2 text-amber-400 text-[11px]">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span>Chat activo pero sin tools registradas.</span>
          <button @click="syncInstance(inst)" class="underline hover:text-amber-300 font-medium">Sincronizar</button>
        </div>
        <div v-if="inst.available_in_reactive && !inst.reactive_mcp_source_id" class="mt-2 flex items-center gap-2 text-amber-400 text-[11px]">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span>Eventos activos pero sin tools registradas.</span>
          <button @click="syncInstance(inst)" class="underline hover:text-amber-300 font-medium">Sincronizar</button>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-2">
          <button
            @click="deleteInstance(inst)"
            class="ml-auto p-2 text-[#4a4a4a] hover:text-red-400 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          </button>
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
