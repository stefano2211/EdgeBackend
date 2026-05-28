<script setup lang="ts">
import { ref, onMounted } from 'vue'
import integrationService, { type IntegrationInstance } from '@/services/integrationService'
import { reactiveCredentialService } from '@/services/reactiveCredentialService'

const integrationInstances = ref<IntegrationInstance[]>([])
const reactiveCredentials = ref<any[]>([])
const isLoading = ref(true)

async function loadData() {
  isLoading.value = true
  try {
    const [instRes, credRes] = await Promise.all([
      integrationService.listInstances(),
      reactiveCredentialService.list(),
    ])
    integrationInstances.value = instRes
    reactiveCredentials.value = credRes
  } catch (e) {
    console.error('Failed to load credentials', e)
  } finally {
    isLoading.value = false
  }
}

async function rotateIntegrationCredentials(instanceId: number) {
  if (!confirm('¿Rotar credenciales? Se eliminarán las actuales y deberás configurar de nuevo.')) return
  try {
    await integrationService.deleteInstance(instanceId)
    await loadData()
  } catch (e) {
    console.error('Failed to rotate', e)
  }
}

  async function deleteReactiveCredential(id: number) {
  if (!confirm('¿Eliminar esta credencial permanentemente?')) return
  try {
    await reactiveCredentialService.remove(id)
    reactiveCredentials.value = reactiveCredentials.value.filter(c => c.id !== id)
  } catch (e) {
    console.error('Failed to delete credential', e)
  }
}

onMounted(loadData)
</script>

<template>
  <div class="px-6 py-6 max-w-6xl mx-auto space-y-8 h-full overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h2 class="text-2xl font-bold text-white tracking-tight">Credenciales</h2>
        <p class="text-[#7a7a7a] text-sm mt-1">Gestiona todas tus credenciales de integraciones y automatización.</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="py-20 text-center">
      <svg class="animate-spin w-8 h-8 text-violet-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
      <p class="text-[#7a7a7a]">Cargando credenciales...</p>
    </div>

    <template v-else>
      <!-- Integration Credentials -->
      <section>
        <h3 class="text-[#7a7a7a] text-[11px] font-bold uppercase tracking-widest mb-5 ml-1 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          Integraciones (MCP)
        </h3>

        <div v-if="integrationInstances.length === 0" class="py-10 bg-white/[0.01] border border-dashed border-white/5 rounded-2xl text-center">
          <p class="text-[#4a4a4a] text-sm">No hay credenciales de integraciones.</p>
        </div>

        <div v-else class="grid grid-cols-1 gap-4">
          <div
            v-for="inst in integrationInstances"
            :key="inst.id"
            class="bg-[#2f2f2f]/30 border border-white/5 rounded-2xl p-4 flex items-center justify-between group hover:border-white/10 transition-all"
          >
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center text-violet-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
              </div>
              <div>
                <h4 class="text-white font-medium text-sm">{{ inst.instance_name }}</h4>
                <p class="text-[#4a4a4a] text-[12px]">{{ inst.catalog?.name }} — {{ inst.catalog?.auth_type }}</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-[11px] text-[#4a4a4a]">{{ inst.catalog?.auth_type }}</span>
              <button
                @click="rotateIntegrationCredentials(inst.id)"
                class="px-3 py-1.5 text-[11px] font-medium text-amber-400 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 rounded-lg transition-all"
              >
                Rotar
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Separator -->
      <div class="border-t border-white/[0.06] my-8"></div>

      <!-- Reactive (VL/Browser) Credentials -->
      <section>
        <h3 class="text-[#7a7a7a] text-[11px] font-bold uppercase tracking-widest mb-5 ml-1 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Automatización (Browser/VL)
        </h3>

        <div v-if="reactiveCredentials.length === 0" class="py-10 bg-white/[0.01] border border-dashed border-white/5 rounded-2xl text-center">
          <p class="text-[#4a4a4a] text-sm">No hay credenciales de automatización.</p>
          <router-link to="/reactive/credentials" class="text-violet-400 font-medium hover:text-violet-300 transition-colors text-sm mt-2 inline-block">
            Gestionar en Reactive &rarr;
          </router-link>
        </div>

        <div v-else class="grid grid-cols-1 gap-4">
          <div
            v-for="cred in reactiveCredentials"
            :key="cred.id"
            class="bg-[#2f2f2f]/30 border border-white/5 rounded-2xl p-4 flex items-center justify-between group hover:border-white/10 transition-all"
          >
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11h18v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V11zm4 0V7a5 5 0 0 1 10 0v4"/></svg>
              </div>
              <div>
                <h4 class="text-white font-medium text-sm">{{ cred.name }}</h4>
                <p class="text-[#4a4a4a] text-[12px] font-mono">{{ cred.key_identifier }}</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-[11px] text-[#4a4a4a]">{{ new Date(cred.created_at).toLocaleDateString() }}</span>
              <button
                @click="deleteReactiveCredential(cred.id)"
                class="p-2 text-[#3a3a3a] hover:text-red-400 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.1); }
</style>
