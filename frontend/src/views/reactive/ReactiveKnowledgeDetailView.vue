<template>
  <div class="h-full flex flex-col pt-6 overflow-hidden bg-[#0a0a0a]">
    <!-- Header Section -->
    <header class="px-8 mb-8 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-5">
        <router-link 
          to="/resources/knowledge" 
          class="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/[0.08] flex items-center justify-center text-[#7a7a7a] hover:text-white hover:bg-white/[0.08] transition-all group"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="group-hover:-translate-x-0.5 transition-transform"><path d="m15 18-6-6 6-6"/></svg>
        </router-link>
        
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/5">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>
          </div>
          <div>
            <div v-if="loading && !kb" class="h-8 w-64 bg-white/5 rounded-lg animate-pulse mb-1"></div>
            <h2 v-else class="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
              {{ kb?.name }}
              <span v-if="kb?.documents" class="text-[11px] px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded uppercase tracking-widest font-bold">
                {{ kb.documents.length }} Docs
              </span>
            </h2>
            <div v-if="loading && !kb" class="h-4 w-48 bg-white/5 rounded-lg animate-pulse"></div>
            <p v-else class="text-[13px] text-[#7a7a7a] font-medium">
              {{ kb?.description || 'Curated repository for event automation analysis.' }}
            </p>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <input 
          type="file" 
          ref="fileInput" 
          class="hidden" 
          accept=".pdf,.doc,.docx,.json,.txt"
          @change="onFileChange"
        >
        <button 
          @click="triggerFileInput"
          :disabled="loading || uploading"
          class="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-black font-bold px-6 py-2.5 rounded-xl transition-all shadow-lg shadow-emerald-500/20 active:scale-95 disabled:opacity-30 text-[13px]"
        >
          <svg v-if="uploading" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
          Add Document
        </button>
      </div>
    </header>

    <!-- Content Area -->
    <div class="flex-1 overflow-hidden px-8 pb-8 flex flex-col">
      <div class="bg-white/[0.02] border border-white/[0.05] rounded-[2rem] flex-1 flex flex-col overflow-hidden backdrop-blur-sm relative">
        
        <!-- Loading Overlay for Table -->
        <div v-if="loading && kb" class="absolute inset-0 bg-black/20 backdrop-blur-[2px] z-20 flex items-center justify-center">
          <svg class="animate-spin h-8 w-8 text-emerald-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        </div>

        <!-- Empty Documents State -->
        <div v-if="!loading && (!kb?.documents || kb.documents.length === 0)" class="flex-1 flex flex-col items-center justify-center py-20 px-8 text-center">
          <div class="w-24 h-24 rounded-full bg-emerald-500/5 border border-emerald-500/10 flex items-center justify-center mb-6 animate-float">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-500/20"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18h.01"/><path d="M12 12V8"/></svg>
          </div>
          <h3 class="text-xl font-bold text-white mb-2">Knowledge is empty</h3>
          <p class="text-[14px] text-[#7a7a7a] mb-8 max-w-sm leading-relaxed">This collection has no documents yet. Upload SOPs, manuals, or logs to empower the reactive AI with context.</p>
          <button 
            @click="triggerFileInput"
            class="text-[13px] font-bold bg-white/5 hover:bg-white/10 text-white border border-white/10 px-8 py-3 rounded-xl transition-all active:scale-95"
          >
            Start Uploading
          </button>
        </div>

        <!-- Table View -->
        <div v-else class="flex-1 overflow-y-auto custom-scrollbar">
          <table class="w-full text-left border-collapse">
            <thead class="sticky top-0 z-10">
              <tr class="bg-[#121212]/80 backdrop-blur-md">
                <th class="px-8 py-5 text-[11px] font-bold text-[#4a4a4a] uppercase tracking-widest border-b border-white/[0.03]">Filename</th>
                <th class="px-8 py-5 text-[11px] font-bold text-[#4a4a4a] uppercase tracking-widest border-b border-white/[0.03]">Status</th>
                <th class="px-8 py-5 text-[11px] font-bold text-[#4a4a4a] uppercase tracking-widest border-b border-white/[0.03]">Added</th>
                <th class="px-8 py-5 text-right border-b border-white/[0.03]"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-white/[0.02]">
              <tr 
                v-for="doc in kb?.documents" 
                :key="doc.id" 
                class="group hover:bg-white/[0.02] transition-colors"
              >
                <td class="px-8 py-5">
                  <div class="flex items-center gap-4">
                    <div class="w-10 h-10 rounded-xl bg-[#1a1a1a] border border-white/[0.05] flex items-center justify-center text-[#7a7a7a] group-hover:text-emerald-400 group-hover:border-emerald-500/20 transition-all">
                      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
                    </div>
                    <div>
                      <div class="text-[14px] font-semibold text-white tracking-tight group-hover:text-emerald-400 transition-colors">{{ doc.filename }}</div>
                      <div class="text-[11px] text-[#4a4a4a] font-mono mt-0.5 tracking-tight">{{ doc.file_id?.substring(0, 12) }}...</div>
                    </div>
                  </div>
                </td>
                <td class="px-8 py-5">
                  <div class="flex items-center gap-2">
                    <div class="w-1.5 h-1.5 rounded-full" :class="doc.status === 'indexed' || doc.status === 'completed' ? 'bg-emerald-400' : 'bg-yellow-400 animate-pulse'"></div>
                    <span class="text-[12px] font-medium" :class="doc.status === 'indexed' || doc.status === 'completed' ? 'text-emerald-400/80' : 'text-yellow-400/80'">
                      {{ doc.status || 'Processing' }}
                    </span>
                  </div>
                </td>
                <td class="px-8 py-5 text-[13px] text-[#7a7a7a] font-medium">
                  {{ formatDate(doc.created_at) }}
                </td>
                <td class="px-8 py-5 text-right">
                  <button 
                    @click="deleteDocument(doc.id)"
                    class="p-2.5 text-[#333] hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Upload Progress Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="uploading" class="fixed inset-0 bg-black/90 backdrop-blur-xl z-[10000] flex items-center justify-center p-4">
          <div class="bg-[#141414] border border-white/[0.08] rounded-[2.5rem] w-full max-w-[420px] p-10 flex flex-col items-center text-center shadow-2xl relative overflow-hidden">
            <!-- Decoration -->
            <div class="absolute -right-20 -top-20 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl"></div>

            <div class="w-16 h-16 bg-emerald-500/10 text-emerald-400 rounded-2xl flex items-center justify-center mb-6 border border-emerald-500/20 shadow-lg shadow-emerald-500/5">
              <svg class="animate-spin w-8 h-8" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            </div>
            <h3 class="text-2xl font-bold text-white mb-2">{{ uploadStatusText }}</h3>
            <p class="text-[14px] text-[#7a7a7a] mb-8 leading-relaxed">Transforming raw data into neural insights for event processing...</p>
            
            <div class="w-full bg-white/5 rounded-full h-3 overflow-hidden border border-white/5 p-0.5">
              <div 
                class="bg-emerald-500 h-full rounded-full transition-all duration-500 ease-out shadow-lg shadow-emerald-500/40"
                :style="{ width: `${uploadProgress}%` }"
              ></div>
            </div>
            <div class="mt-3 text-[11px] font-bold text-emerald-500/50 uppercase tracking-widest">{{ uploadProgress }}% Synchronized</div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { knowledgeService, type KnowledgeBaseDetail } from '@/services/knowledgeService'
import { documentService } from '@/services/documentService'

const props = defineProps<{
  id: string
}>()

const kb = ref<KnowledgeBaseDetail | null>(null)
const loading = ref(true)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadProgress = ref(0)
const uploadStatusText = ref('')

async function fetchKnowledgeBase() {
  try {
    loading.value = true
    kb.value = await knowledgeService.getKnowledgeBase(props.id)
  } catch (error) {
    console.error('Failed to fetch kb details:', error)
    alert('Error al cargar la colección')
  } finally {
    loading.value = false
  }
}

function triggerFileInput() {
  fileInput.value?.click()
}

async function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  
  const file = target.files[0] as File
  if (!file) return
  
  try {
    uploading.value = true
    uploadProgress.value = 5
    uploadStatusText.value = 'Initializing Upload'
    const data = await knowledgeService.uploadDocumentToKnowledgeBase(props.id, file)
    
    await pollTaskStatus(String(data.id))
    await fetchKnowledgeBase()
    
  } catch (error) {
    console.error('Failed to upload document:', error)
    alert('Error al subir el documento')
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function pollTaskStatus(docId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const response = await documentService.getStatus(docId)
        const status = response.status
        const metaStatus = response.info?.status || ''

        if (status === 'FAILURE') {
          clearInterval(interval)
          reject(new Error('Task failed'))
          return
        }

        if (status === 'SUCCESS' || metaStatus === 'indexed') {
          uploadProgress.value = 100
          uploadStatusText.value = 'Sync Complete'
          clearInterval(interval)
          setTimeout(() => resolve('SUCCESS'), 800)
          return
        }

        if (status === 'PROGRESS') {
           uploadProgress.value = 60
           uploadStatusText.value = 'Vectorizing & Analyzing'
        } else if (status === 'PENDING') {
           uploadProgress.value = 20
           uploadStatusText.value = 'Queueing Data'
        }
      } catch (err) {
        console.error('Polling error', err)
      }
    }, 1500)
  })
}

async function deleteDocument(docId: string) {
  if (!confirm('Are you sure you want to delete this document?')) {
    return
  }

  try {
    loading.value = true
    await documentService.deleteDocument(docId)
    await fetchKnowledgeBase()
  } catch (error) {
    console.error('Failed to delete document:', error)
    alert('Error al eliminar el documento')
  } finally {
    loading.value = false
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

onMounted(() => {
  fetchKnowledgeBase()
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.1);
}

@keyframes float {
  0% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
  100% { transform: translateY(0px); }
}
.animate-float {
  animation: float 4s ease-in-out infinite;
}

/* Modal Animations */
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.3s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
</style>
