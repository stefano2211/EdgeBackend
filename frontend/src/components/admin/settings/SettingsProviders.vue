<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SettingToggle from './SettingToggle.vue'
import { adminService, type SystemSettingsGeneral } from '@/services/adminService'

const isLoading = ref(true)
const isSaving = ref(false)

// Configuración de Proveedores
const ollamaEnabled = ref(true)
const ollamaBaseUrl = ref('http://ollama:11434')

const openrouterEnabled = ref(false)
const openrouterApiKey = ref('')
const openrouterBaseUrl = ref('https://openrouter.ai/api/v1')

onMounted(async () => {
  try {
    const settings = await adminService.getGeneralSettings()
    ollamaEnabled.value = settings.ollama_enabled
    ollamaBaseUrl.value = settings.ollama_base_url
    openrouterEnabled.value = settings.openrouter_enabled
    openrouterApiKey.value = settings.openrouter_api_key || ''
    openrouterBaseUrl.value = settings.openrouter_base_url
  } catch (error) {
    console.error('Failed to load provider settings:', error)
  } finally {
    isLoading.value = false
  }
})

async function save() {
  if (isSaving.value) return
  isSaving.value = true
  
  try {
    const payload: Partial<SystemSettingsGeneral> = {
      ollama_enabled: ollamaEnabled.value,
      ollama_base_url: ollamaBaseUrl.value,
      openrouter_enabled: openrouterEnabled.value,
      openrouter_api_key: openrouterApiKey.value,
      openrouter_base_url: openrouterBaseUrl.value
    }
    
    await adminService.updateGeneralSettings(payload as any)
    alert('Provider settings saved successfully')
  } catch (error) {
    console.error('Failed to save settings:', error)
    alert('Failed to save Provider settings')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="space-y-8 pb-10 relative">
    
    <div v-if="isLoading" class="absolute inset-0 z-10 bg-[#212121]/80 backdrop-blur-sm flex items-center justify-center">
      <div class="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Ollama Settings -->
    <div class="bg-white/5 p-6 rounded-2xl border border-white/[0.05]">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center text-orange-500">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 3 4 8 5-5 5 15H2L8 3z"/></svg>
          </div>
          <div>
            <h3 class="text-[15px] font-semibold text-white">Ollama</h3>
            <p class="text-[12px] text-[#7a7a7a]">Local LLM runner integration</p>
          </div>
        </div>
        <SettingToggle v-model="ollamaEnabled" />
      </div>

      <div v-if="ollamaEnabled" class="space-y-4 pt-4 border-t border-white/[0.05] animate-in fade-in slide-in-from-top-2 duration-300">
        <div>
          <label class="block text-[12px] font-medium text-[#7a7a7a] mb-1.5 ml-1">Base URL</label>
          <input 
            v-model="ollamaBaseUrl"
            type="text" 
            placeholder="http://localhost:11434"
            class="w-full bg-[#1a1a1a] border border-white/[0.05] rounded-xl px-4 py-2.5 text-[13px] text-white focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>
      </div>
    </div>

    <!-- OpenRouter Settings -->
    <div class="bg-white/5 p-6 rounded-2xl border border-white/[0.05]">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-500">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
          </div>
          <div>
            <h3 class="text-[15px] font-semibold text-white">OpenRouter</h3>
            <p class="text-[12px] text-[#7a7a7a]">Unified API for broad LLM access</p>
          </div>
        </div>
        <SettingToggle v-model="openrouterEnabled" />
      </div>

      <div v-if="openrouterEnabled" class="space-y-4 pt-4 border-t border-white/[0.05] animate-in fade-in slide-in-from-top-2 duration-300">
        <div>
          <label class="block text-[12px] font-medium text-[#7a7a7a] mb-1.5 ml-1">API Key</label>
          <input 
            v-model="openrouterApiKey"
            type="password" 
            placeholder="sk-or-v1-..."
            class="w-full bg-[#1a1a1a] border border-white/[0.05] rounded-xl px-4 py-2.5 text-[13px] text-white focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>
        <div>
          <label class="block text-[12px] font-medium text-[#7a7a7a] mb-1.5 ml-1">Base URL</label>
          <input 
            v-model="openrouterBaseUrl"
            type="text" 
            placeholder="https://openrouter.ai/api/v1"
            class="w-full bg-[#1a1a1a] border border-white/[0.05] rounded-xl px-4 py-2.5 text-[13px] text-white focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>
      </div>
    </div>

    <!-- Save Button -->
    <div class="fixed bottom-6 right-6">
      <button
        @click="save"
        :disabled="isLoading || isSaving"
        class="bg-white hover:bg-white/90 text-black text-[14px] font-semibold px-6 py-3 rounded-full shadow-lg transition-transform hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 flex items-center gap-2"
      >
        <span v-if="isSaving" class="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin inline-block"></span>
        {{ isSaving ? 'Saving...' : 'Save' }}
      </button>
    </div>
  </div>
</template>
