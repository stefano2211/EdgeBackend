<script setup lang="ts">
import { ref, inject, type Ref, onMounted } from 'vue'
import { documentService } from '@/services/documentService'
import toolService, { type ToolConfig, type MCPSource } from '@/services/toolService'
import VariableAutocomplete from '@/components/common/VariableAutocomplete.vue'
import RichVariablesInput from '@/components/common/RichVariablesInput.vue'
import type { KnowledgeBase } from '@/services/knowledgeService'

const knowledgeBases = inject<Ref<KnowledgeBase[]>>('knowledgeBases', ref([]))
const activeKnowledgeBaseId = inject<Ref<string | null>>('activeKnowledgeBaseId', ref(null))
const selectKb = inject<(id: string | null) => void>('selectKb', () => {})

const mcpSources = inject<Ref<any[]>>('mcpSources', ref([]))
const activeMcpSourceId = inject<Ref<string | null>>('activeMcpSourceId', ref(null))
const selectMcpSource = inject<(id: string | null) => void>('selectMcpSource', () => {})

const showUnifiedDropdown = ref(false)
const activeSubmenu = ref<'knowledge' | 'mcp' | null>(null)

const props = defineProps<{
  disabled?: boolean
}>()

const chatInput = ref('')
const isUploading = ref(false)
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadProgress = ref(0)
const uploadStatusText = ref('')
const currentPollingTaskId = ref<string | null>(null)

const availableTools = ref<ToolConfig[]>([])
const availableSources = ref<MCPSource[]>([])
const cursorPos = ref(0)
const richInputRef = ref<InstanceType<typeof RichVariablesInput> | null>(null)

onMounted(async () => {
  try {
    const [tools, sources] = await Promise.all([
      toolService.listTools(),
      toolService.listSources()
    ])
    availableTools.value = tools
    availableSources.value = sources
  } catch (err) {
    console.error('Failed to load tools and sources for autocomplete', err)
  }
})

function handleVariableInsert(newQuery: string, newPos: number) {
  chatInput.value = newQuery
  cursorPos.value = newPos
  setTimeout(() => {
    if (richInputRef.value) {
      richInputRef.value.focusAndSetCursor(newPos)
    }
  }, 20)
}

const emit = defineEmits<{
  (e: 'send', message: string): void
}>()

function handleSend() {
  if ((!chatInput.value.trim() && !selectedFile.value) || props.disabled || isUploading.value) return
  
  if (selectedFile.value) {
    handleFileUpload()
  } else {
    emit('send', chatInput.value)
    chatInput.value = ''
  }
}

async function handleFileUpload() {
  if (!selectedFile.value) return
  
  isUploading.value = true
  uploadProgress.value = 5
  uploadStatusText.value = 'Iniciando subida...'
  
  try {
    const data = await documentService.uploadFile(
      selectedFile.value,
      activeKnowledgeBaseId.value || undefined
    )
    currentPollingTaskId.value = data.id
    
    const finalStatus = await pollTaskStatus(data.id)
    
    const successMsg = `[Archivo subido: ${selectedFile.value.name}] (Listo y vectorizado)`
    emit('send', chatInput.value ? `${chatInput.value}\n\n${successMsg}` : successMsg)
    
    selectedFile.value = null
    chatInput.value = ''
    uploadProgress.value = 0
    if (fileInput.value) fileInput.value.value = ''
  } catch (error) {
    console.error('Upload failed', error)
    alert('Error al procesar o subir el archivo. Intenta de nuevo.')
    uploadProgress.value = 0
  } finally {
    isUploading.value = false
    currentPollingTaskId.value = null
  }
}

async function pollTaskStatus(taskId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const response = await documentService.getStatus(taskId)
        const status = response.status
        const metaStatus = response.info?.status || ''

        if (status === 'FAILURE') {
          clearInterval(interval)
          reject(new Error('Task failed'))
          return
        }

        if (status === 'SUCCESS' || metaStatus === 'completado') {
          uploadProgress.value = 100
          uploadStatusText.value = '¡Completado!'
          clearInterval(interval)
          setTimeout(() => resolve('SUCCESS'), 800)
          return
        }

        if (status === 'PROGRESS') {
           if (metaStatus === 'descargando') {
             uploadProgress.value = 30
             uploadStatusText.value = 'Descargando...'
           } else if (metaStatus === 'procesando') {
             uploadProgress.value = 70
             uploadStatusText.value = 'Procesando y vectorizando...'
           }
        } else if (status === 'PENDING') {
           uploadProgress.value = 15
           uploadStatusText.value = 'En cola...'
        }
      } catch (err) {
        console.error('Polling error', err)
      }
    }, 1500)
  })
}

function triggerFileInput() {
  showUnifiedDropdown.value = false
  fileInput.value?.click()
}

function onFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    selectedFile.value = target.files[0]
  }
}

function removeSelectedFile() {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}
</script>
<template>
  <div class="absolute bottom-0 left-0 right-0 px-4 md:px-8 bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a]/95 to-transparent pt-8 pb-4">
    <div class="max-w-3xl mx-auto">
      
      <!-- File Preview -->
      <div v-if="selectedFile" class="mb-3 px-2 flex animate-in z-50 relative pointer-events-auto">
        <div class="bg-[#1c1c1c] border border-white/[0.06] rounded-2xl px-4 py-3 flex flex-col gap-3 shadow-xl w-72 relative overflow-hidden">
          <div class="flex items-start justify-between relative z-10">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center shrink-0 border border-blue-500/20">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/></svg>
              </div>
              <div class="flex flex-col overflow-hidden">
                <span class="text-[13px] font-medium text-[#ececec] truncate pr-2">{{ selectedFile.name }}</span>
                <span class="text-[11px] text-[#7a7a7a] font-medium mt-0.5">{{ isUploading ? uploadStatusText : `${(selectedFile.size / 1024).toFixed(1)} KB` }}</span>
              </div>
            </div>
            <button v-if="!isUploading" @click="removeSelectedFile" class="shrink-0 p-1.5 hover:bg-white/10 rounded-full text-[#7a7a7a] hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>
          <div v-if="isUploading" class="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
            <div class="bg-blue-500 h-1.5 rounded-full transition-all duration-500 ease-out" :style="{ width: `${uploadProgress}%` }"></div>
          </div>
        </div>
      </div>

      <!-- Input Container -->
      <div class="bg-[#0f0f0f] border border-white/[0.06] rounded-2xl p-3 flex flex-col shadow-lg transition-all focus-within:border-white/20 group">
        <input 
          type="file" 
          ref="fileInput" 
          class="hidden" 
          @change="onFileSelected"
          accept=".pdf,.doc,.docx,.json"
        />
        
        <div class="relative w-full">
          <VariableAutocomplete 
            :sources="availableSources"
            :tools="availableTools" 
            :query="chatInput" 
            :cursorPosition="cursorPos" 
            @insert="handleVariableInsert" 
            @close="cursorPos = 0" 
          />
          <RichVariablesInput 
            ref="richInputRef"
            v-model="chatInput"
            @enter="handleSend"
            @cursor-update="cursorPos = $event"
            placeholder="How can I help you today?"
            :disabled="disabled || isUploading"
            class="min-h-[44px]"
          />
        </div>
        
        <div class="flex items-center justify-between px-2 pt-1">
          <div class="flex gap-0.5 items-center relative">
            <!-- Unified Context Menu (Paperclip) -->
            <div class="relative flex items-center">
              <button 
                type="button" 
                @click="showUnifiedDropdown = !showUnifiedDropdown"
                class="p-2 rounded-full transition-all flex items-center justify-center active:scale-95 relative"
                :class="(activeKnowledgeBaseId || activeMcpSourceId) ? 'text-white bg-white/10' : 'text-[#b4b4b4] hover:text-white hover:bg-white/5'"
                title="Adjuntar y Contexto"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                <!-- Indicator dot if context active -->
                <div v-if="activeKnowledgeBaseId || activeMcpSourceId" class="absolute top-1 right-1 w-2 h-2 bg-indigo-500 rounded-full border border-[#2f2f2f]"></div>
              </button>

              <!-- Unified Nested Dropdown -->
              <div v-if="showUnifiedDropdown" 
                class="absolute bottom-[calc(100%+12px)] left-0 w-64 bg-[#1c1c1c] border border-white/[0.06] rounded-2xl shadow-2xl py-2 z-50 animate-in"
                @mouseleave="activeSubmenu = null"
              >
                <!-- Group 1: Files -->
                <div class="px-2">
                  <button 
                    @click="triggerFileInput"
                    class="w-full text-left px-3 py-2.5 text-[14px] text-[#ececec] hover:bg-white/[0.04] rounded-xl transition-colors flex items-center gap-3 group/item"
                  >
                    <div class="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400 group-hover/item:bg-indigo-500/20 transition-colors">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
                    </div>
                    <span class="font-medium">Subir Archivo</span>
                  </button>
                </div>

                <div class="h-px bg-white/5 my-1.5 mx-2"></div>

                <!-- Group 2: Contexts -->
                <div class="px-2 space-y-0.5">
                  <!-- Knowledge Submenu Trigger -->
                  <div class="relative">
                    <button 
                      @mouseenter="activeSubmenu = 'knowledge'"
                      class="w-full text-left px-3 py-2.5 text-[14px] text-[#ececec] hover:bg-white/[0.04] rounded-xl transition-colors flex items-center justify-between group/item"
                      :class="{ 'bg-white/[0.04]': activeSubmenu === 'knowledge' }"
                    >
                      <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-400 group-hover/item:bg-amber-500/20 transition-colors">
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/></svg>
                        </div>
                        <div class="flex flex-col">
                          <span class="font-medium">Conocimiento</span>
                          <span class="text-[10px] text-[#7a7a7a]">{{ activeKnowledgeBaseId ? 'Personalizado' : 'Sin Contexto' }}</span>
                        </div>
                      </div>
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-[#7a7a7a]"><path d="m9 18 6-6-6-6"/></svg>
                    </button>

                    <!-- Knowledge Submenu -->
                    <div v-if="activeSubmenu === 'knowledge'"
                      class="absolute left-[calc(100%+8px)] bottom-0 w-64 bg-[#1c1c1c] border border-white/[0.06] rounded-2xl shadow-2xl py-2 z-50 animate-in"
                    >
                      <div class="px-3 py-1.5 text-[10px] font-bold text-[#7a7a7a] uppercase tracking-widest mb-1">Colecciones (RAG)</div>
                      <div class="max-h-[240px] overflow-y-auto px-1 group">
                        <button 
                          @click="selectKb(null); showUnifiedDropdown = false"
                          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex items-center justify-between mb-0.5"
                          :class="!activeKnowledgeBaseId ? 'bg-white/10 text-white' : 'text-[#b4b4b4] hover:bg-white/5'"
                        >
                          <span class="flex items-center gap-2">
                             <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" x2="19.07" y1="4.93" y2="19.07"/></svg>
                             Sin Conocimiento
                          </span>
                          <svg v-if="!activeKnowledgeBaseId" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-indigo-400"><path d="M20 6 9 17l-5-5"/></svg>
                        </button>
                        <button 
                          v-for="kb in knowledgeBases" :key="kb.id"
                          @click="selectKb(kb.id); showUnifiedDropdown = false"
                          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex items-center justify-between mb-0.5"
                          :class="activeKnowledgeBaseId === kb.id ? 'bg-white/10 text-white' : 'text-[#b4b4b4] hover:bg-white/5'"
                        >
                          <span class="flex items-center gap-2 truncate">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/></svg>
                            <span class="truncate">{{ kb.name }}</span>
                          </span>
                          <svg v-if="activeKnowledgeBaseId === kb.id" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-indigo-400"><path d="M20 6 9 17l-5-5"/></svg>
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- MCP Submenu Trigger -->
                  <div class="relative">
                    <button 
                      @mouseenter="activeSubmenu = 'mcp'"
                      class="w-full text-left px-3 py-2.5 text-[14px] text-[#ececec] hover:bg-white/[0.04] rounded-xl transition-colors flex items-center justify-between group/item"
                      :class="{ 'bg-white/[0.04]': activeSubmenu === 'mcp' }"
                    >
                      <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400 group-hover/item:bg-emerald-500/20 transition-colors">
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/></svg>
                        </div>
                        <div class="flex flex-col">
                          <span class="font-medium">Herramientas (MCP)</span>
                          <span class="text-[10px] text-[#7a7a7a]">
                            {{ activeMcpSourceId === 'none' ? 'Desactivadas' : (activeMcpSourceId ? 'Fuente Específica' : 'Todas Activas') }}
                          </span>
                        </div>
                      </div>
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-[#7a7a7a]"><path d="m9 18 6-6-6-6"/></svg>
                    </button>

                    <!-- MCP Submenu -->
                    <div v-if="activeSubmenu === 'mcp'"
                      class="absolute left-[calc(100%+8px)] bottom-0 w-64 bg-[#1c1c1c] border border-white/[0.06] rounded-2xl shadow-2xl py-2 z-50 animate-in"
                    >
                      <div class="px-3 py-1.5 text-[10px] font-bold text-[#7a7a7a] uppercase tracking-widest mb-1">Fuentes de Datos</div>
                      <div class="max-h-[240px] overflow-y-auto px-1">
                        <button 
                          @click="selectMcpSource('none'); showUnifiedDropdown = false"
                          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex items-center justify-between mb-0.5"
                          :class="activeMcpSourceId === 'none' ? 'bg-white/10 text-white' : 'text-[#b4b4b4] hover:bg-white/5'"
                        >
                          <span class="flex items-center gap-2">
                             <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/><line x1="8" y1="2" x2="8" y2="4"/><line x1="12" y1="2" x2="12" y2="4"/></svg>
                             Sin Herramientas
                          </span>
                          <svg v-if="activeMcpSourceId === 'none'" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-indigo-400"><path d="M20 6 9 17l-5-5"/></svg>
                        </button>
                        <button 
                          @click="selectMcpSource(null); showUnifiedDropdown = false"
                          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex items-center justify-between mb-0.5"
                          :class="activeMcpSourceId === null ? 'bg-white/10 text-white' : 'text-[#b4b4b4] hover:bg-white/5'"
                        >
                          <span class="flex items-center gap-2">
                             <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"/></svg>
                             Todas las Fuentes
                          </span>
                          <svg v-if="activeMcpSourceId === null" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-indigo-400"><path d="M20 6 9 17l-5-5"/></svg>
                        </button>
                        <button 
                          v-for="source in mcpSources" :key="source.id"
                          @click="selectMcpSource(source.id); showUnifiedDropdown = false"
                          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex items-center justify-between mb-0.5"
                          :class="activeMcpSourceId === source.id ? 'bg-white/10 text-white' : 'text-[#b4b4b4] hover:bg-white/5'"
                        >
                          <span class="flex items-center gap-2 truncate pr-2">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/></svg>
                            <span class="truncate">{{ source.name }}</span>
                          </span>
                          <svg v-if="activeMcpSourceId === source.id" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-indigo-400"><path d="M20 6 9 17l-5-5"/></svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <button type="button" class="p-2 text-[#b4b4b4] hover:text-white hover:bg-white/5 rounded-full transition-all flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
            </button>

            <div class="h-4 w-px bg-white/10 mx-1.5"></div>

            <!-- Visual indicators of active context -->
            <div class="flex items-center gap-1.5 overflow-hidden">
                <span v-if="activeKnowledgeBaseId" class="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 text-[11px] font-medium rounded-md border border-indigo-500/20 truncate max-w-[100px]">
                    {{ knowledgeBases.find(k => k.id === activeKnowledgeBaseId)?.name }}
                </span>
                <span v-if="activeMcpSourceId && activeMcpSourceId !== 'none'" class="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[11px] font-medium rounded-md border border-emerald-500/20 truncate max-w-[100px]">
                    {{ mcpSources.find(s => s.id === activeMcpSourceId)?.name }}
                </span>
                <span v-if="activeMcpSourceId === 'none'" class="px-2 py-0.5 bg-red-500/10 text-red-400 text-[11px] font-medium rounded-md border border-red-500/20">
                    Sin Herramientas
                </span>
            </div>
          </div>
          
          <div class="flex items-center gap-1.5">
            <!-- Voice -->
            <button type="button" class="p-2 text-[#b4b4b4] hover:text-white hover:bg-white/5 rounded-full transition-all active:scale-95">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
            </button>
            
            <!-- Send -->
            <button 
              type="button"
              @click="handleSend"
              class="p-2.5 bg-white/5 border border-white/10 text-white hover:bg-white/10 rounded-full transition-all disabled:bg-white/5 disabled:text-[#555] disabled:cursor-not-allowed active:scale-90 flex items-center justify-center"
              :disabled="(!chatInput.trim() && !selectedFile) || disabled || isUploading"
            >
              <svg v-if="!isUploading" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
              <svg v-else class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </button>
          </div>
        </div>
      </div>
      
      <div class="text-center mt-3 text-[11px] text-[#7a7a7a] tracking-wide">
        Aura AI Agent can make mistakes. Consider verifying important information.
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-in {
  animation: fadeIn 0.3s ease-out forwards;
}
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
