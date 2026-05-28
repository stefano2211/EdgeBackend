<template>
  <div class="space-y-6 max-w-5xl mx-auto">
    <!-- Header -->
    <header class="flex items-start justify-between">
      <div class="flex items-center gap-4">
        <router-link to="/workspace/knowledge" class="p-2 hover:bg-white/10 rounded-xl transition-colors text-gray-400 hover:text-white shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-arrow-left"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>
        </router-link>
        
        <div>
          <div v-if="loading" class="h-8 w-64 bg-white/10 rounded-lg animate-pulse mb-2"></div>
          <h2 v-else class="text-[28px] font-semibold tracking-tight text-white flex items-center gap-2 mb-1.5">
            {{ kb?.name }}
          </h2>
          
          <div v-if="loading" class="h-4 w-48 bg-white/5 rounded-lg animate-pulse"></div>
          <p v-else class="text-gray-400 text-[15px]">
            {{ kb?.description || 'Sin descripción' }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <input 
          type="file" 
          ref="fileInput" 
          class="hidden" 
          accept=".pdf,.doc,.docx,.json"
          @change="onFileChange"
        >
        <button 
          @click="triggerFileInput"
          :disabled="loading || uploading"
          class="flex items-center gap-2 bg-white text-black hover:bg-gray-200 font-medium px-4 py-2 rounded-full transition-colors shadow-sm disabled:opacity-50 text-sm"
        >
          <svg v-if="uploading" class="animate-spin -ml-1 mr-1 h-4 w-4 text-black" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-upload"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
          Subir Documento
        </button>
      </div>
    </header>

    <!-- Documents List -->
    <div class="bg-white/[0.02] border border-white/5 rounded-2xl overflow-hidden mt-8 shadow-sm relative">

      <!-- Upload Progress Overlay -->
      <div v-if="uploading" class="absolute inset-0 bg-black/40 backdrop-blur-sm z-10 flex flex-col items-center justify-center p-6">
        <div class="bg-[#1c1c1c] border border-white/10 rounded-2xl p-6 shadow-2xl w-full max-w-sm flex flex-col items-center text-center animate-in fade-in zoom-in-95 duration-200">
          <div class="w-12 h-12 bg-blue-500/10 text-blue-400 rounded-xl flex items-center justify-center mb-4 border border-blue-500/20">
            <svg class="animate-spin w-6 h-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          </div>
          <h3 class="text-white font-medium text-base mb-1">{{ uploadStatusText }}</h3>
          <p class="text-sm text-gray-400 mb-5">Preparando documentos para IA...</p>
          
          <div class="w-full bg-white/5 rounded-full h-2 overflow-hidden border border-white/5">
            <div 
              class="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out"
              :style="{ width: `${uploadProgress}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="p-8 text-center text-gray-500">
        <svg class="animate-spin mx-auto h-8 w-8 text-gray-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        Cargando documentos...
      </div>
      
      <div v-else-if="!kb?.documents || kb.documents.length === 0" class="flex flex-col items-center justify-center py-20 px-4 text-center bg-[#171717] rounded-2xl border border-white/5 shadow-sm mt-8">
        <div class="w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center mb-5 rotate-3 shadow-sm border border-white/5">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-400 -rotate-3"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/></svg>
        </div>
        <h3 class="text-lg font-semibold text-white mb-2">El conocimiento está vacío</h3>
        <p class="text-gray-400 text-[15px] mb-8 max-w-sm mx-auto">Sube archivos PDF o Word para enriquecer esta base de conocimiento.</p>
        <button 
          @click="triggerFileInput"
          class="text-sm font-medium border border-white/10 hover:bg-white/5 text-white px-5 py-2.5 rounded-full transition-colors flex items-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-upload"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
          Subir Documento
        </button>
      </div>

      <table v-else class="w-full text-left text-sm text-gray-300">
        <thead class="text-[12px] uppercase bg-black/20 text-gray-500 border-b border-white/5 font-semibold tracking-wider">
          <tr>
            <th scope="col" class="px-6 py-4">Nombre de Archivo</th>
            <th scope="col" class="px-6 py-4">Fecha de Subida</th>
            <th scope="col" class="px-6 py-4 text-right">Detalles</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="doc in kb.documents" 
            :key="doc.id" 
            class="border-b border-white/5 hover:bg-white/5 transition-colors group"
          >
            <td class="px-6 py-4 font-medium text-gray-200 flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-gray-400 group-hover:text-blue-400 group-hover:bg-blue-500/10 transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-file"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
              </div>
              {{ doc.filename }}
            </td>
            <td class="px-6 py-4 text-[13px] text-gray-500 font-medium">
              {{ formatDate(doc.created_at) }}
            </td>
            <td class="px-6 py-4 text-right flex items-center justify-end gap-3">
              <span class="text-[11px] text-gray-500 bg-black/20 border border-white/5 px-2.5 py-1 rounded-md font-mono">{{ doc.file_id?.substring(0, 8) }}</span>
              <button 
                @click="deleteDocument(doc.id)"
                class="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
                title="Eliminar documento"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash-2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

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
    uploadStatusText.value = 'Iniciando subida...'
    const data = await knowledgeService.uploadDocumentToKnowledgeBase(props.id, file)
    
    await pollTaskStatus(data.id)
    
    // Refresh to get the true db record created by the backend
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

async function pollTaskStatus(taskId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    // We import documentService inline or just use the global api if needed
    // But since it's already set up in documentService, let's import it at the top
    const interval = setInterval(async () => {
      try {
        // use documentService.getStatus (added to imports below)
        const response = await documentService.getStatus(taskId)
        const status = response.status
        const metaStatus = response.info?.status || ''

        if (status === 'FAILURE') {
          clearInterval(interval)
          reject(new Error('Task failed'))
          return
        }

        if (status === 'SUCCESS' || metaStatus === 'indexed') {
          uploadProgress.value = 100
          uploadStatusText.value = 'Completado'
          clearInterval(interval)
          setTimeout(() => resolve('SUCCESS'), 800)
          return
        }

        if (status === 'PROGRESS') {
           uploadProgress.value = 60
           uploadStatusText.value = 'Vectorizando y analizando...'
        } else if (status === 'PENDING') {
           uploadProgress.value = 20
           uploadStatusText.value = 'En cola...'
        }
      } catch (err) {
        console.error('Polling error', err)
      }
    }, 1500)
  })
}

async function deleteDocument(docId: string) {
  if (!confirm('¿Estás seguro de que deseas eliminar este documento de la base de conocimiento? Esta acción también lo removerá del vector store.')) {
    return
  }

  try {
    loading.value = true // Re-use loading state to disable UI
    // Llamar al nuevo método que elimina usando el `file_id` (en backend es `doc_id` del metadata). 
    // Nota: El backend de FastAPI espera doc_id de qdrant, que corresponde a `file_id` del SQLModel en este caso.
    await documentService.deleteDocument(docId)
    await fetchKnowledgeBase() // Refresca la tabla
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
