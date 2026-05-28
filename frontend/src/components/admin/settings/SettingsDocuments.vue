<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SettingInput from './SettingInput.vue'
import { adminService, type SystemSettings } from '@/services/adminService'

// Settings State
const chunkSize = ref('1000')
const chunkOverlap = ref('100')
const searchResults = ref('5')

const isLoading = ref(true)
const isSaving = ref(false)

onMounted(async () => {
  try {
    const settings = await adminService.getSettings()
    chunkSize.value = settings.document_chunk_size.toString()
    chunkOverlap.value = settings.document_chunk_overlap.toString()
    searchResults.value = settings.retrieval_search_results.toString()
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    isLoading.value = false
  }
})

async function save() {
  if (isSaving.value) return
  isSaving.value = true
  
  try {
    const payload: SystemSettings = {
      document_chunk_size: parseInt(chunkSize.value) || 1000,
      document_chunk_overlap: parseInt(chunkOverlap.value) || 100,
      retrieval_search_results: parseInt(searchResults.value) || 5
    }
    
    await adminService.updateSettings(payload)
    alert('Document settings saved successfully')
  } catch (error) {
    console.error('Failed to save settings:', error)
    alert('Failed to save Document settings')
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

    <!-- General -->
    <div>
      <h3 class="text-[15px] font-semibold text-white mb-4">Ingestion Configuration</h3>
      
      <div class="space-y-1">
        <div class="grid grid-cols-2 gap-4">
          <SettingInput 
            v-model="chunkSize"
            label="Chunk Size"
            type="number"
            description="Number of characters per split when processing documents."
          />
          <SettingInput 
            v-model="chunkOverlap"
            label="Chunk Overlap"
            type="number"
            description="Number of overlapping characters between chunks."
          />
        </div>
      </div>
    </div>

    <!-- Retrieval -->
    <div>
      <h3 class="text-[15px] font-semibold text-white mb-4">Retrieval Configuration</h3>
      
      <div class="space-y-1">
        <SettingInput 
          v-model="searchResults"
          label="Search Limit (Top-K)"
          type="number"
          description="How many chunks to retrieve per search query for the Agent's context."
        />
      </div>
    </div>

    <!-- Additional Information -->
    <div class="text-[#7a7a7a] text-[13px] py-6 border border-dashed border-white/[0.08] rounded-2xl flex flex-col items-center justify-center text-center px-6">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mb-3 opacity-50"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
      These settings affect all future document uploads and agent queries.<br/> 
      Modifying chunk sizes will not restrospectively re-chunk already uploaded documents.
    </div>

    <!-- Save Button Floating -->
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
