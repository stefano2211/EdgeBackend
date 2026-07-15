<template>
  <div class="h-full flex flex-col pt-4 overflow-hidden">
    <!-- Section Header -->
    <header class="px-8 mb-6 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-3">
        <h2 class="text-xl font-semibold text-white">Conocimiento</h2>
        <span class="text-[14px] text-[#7a7a7a] font-medium">{{ filteredCollections.length }}</span>
      </div>

      <button 
        @click="showCreateModal = true"
        class="flex items-center gap-2 bg-white text-black hover:bg-gray-200 font-semibold px-4 py-2 rounded-xl transition-colors shrink-0 text-[13px]"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
        Crear colección
      </button>
    </header>

    <!-- Search Section -->
    <div class="px-8 mb-6 shrink-0">
      <div class="relative group">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="absolute left-4 top-1/2 -translate-y-1/2 text-[#7a7a7a] group-focus-within:text-white transition-colors"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <div class="absolute left-11 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none">
          <button class="bg-[#2f2f2f] text-[11px] text-[#7a7a7a] px-2 py-0.5 rounded cursor-default border border-white/5 pointer-events-auto hover:text-white">Todos los documentos</button>
        </div>
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="Buscar conocimiento" 
          class="w-full bg-[#2f2f2f]/30 border border-white/[0.06] rounded-xl pl-[124px] pr-4 py-3 text-[14px] text-[#ececec] placeholder-[#7a7a7a] focus:outline-none focus:border-white/10 focus:bg-[#2f2f2f]/50 transition-all"
        >
      </div>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-y-auto px-8 pb-12 custom-scrollbar">
      <!-- Loading -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="bg-white/5 border border-white/[0.06] rounded-2xl h-48 animate-pulse"></div>
      </div>

      <!-- Empty / No results -->
      <div v-else-if="filteredCollections.length === 0" class="flex flex-col items-center justify-center py-32 text-center">
        <div class="text-4xl mb-4">🧐</div>
        <h3 class="text-lg font-medium text-white mb-2">{{ searchQuery ? 'Sin resultados' : 'No se encontró conocimiento' }}</h3>
        <p class="text-[14px] text-[#7a7a7a] mb-8 max-w-sm">
          {{ searchQuery ? 'Ajusta tu búsqueda o filtro para encontrar lo que buscas.' : 'Crea tu primera colección para agrupar documentos y recuperarlos en tus chats.' }}
        </p>
        <button 
          v-if="!searchQuery"
          @click="showCreateModal = true"
          class="text-[13px] font-bold bg-white/5 hover:bg-white/10 text-white border border-white/10 px-6 py-2.5 rounded-xl transition-all"
        >
          Nueva colección
      </div>

      <!-- Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <router-link
          v-for="kb in filteredCollections"
          :key="kb.id"
          :to="{ name: 'knowledge-detail', params: { id: kb.id } }"
          class="group bg-white/[0.03] hover:bg-white/[0.04] border border-white/[0.06] rounded-xl p-5 transition-all cursor-pointer relative flex flex-col h-52 overflow-hidden hover:border-white/10"
        >
          <div class="flex items-start justify-between mb-3 relative z-10">
            <div class="w-10 h-10 rounded-xl bg-[#171717] flex items-center justify-center border border-white/[0.06] group-hover:border-white/10 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#b4b4b4] group-hover:text-white transition-colors"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>
            </div>
            <button @click.prevent="deleteKb(kb.id)" class="text-[#7a7a7a] hover:text-red-400 p-1.5 hover:bg-white/10 rounded-lg opacity-0 group-hover:opacity-100 transition-all">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            </button>
          </div>
          
          <h3 class="font-semibold text-[15px] text-white mb-1 leading-tight truncate tracking-tight">{{ kb.name }}</h3>
          <p class="text-[#7a7a7a] text-[13px] line-clamp-2 mb-3 flex-grow leading-relaxed">          {{ kb.description || 'Sin descripción para esta colección.' }}</p>
          
          <!-- Context Toggles -->
          <div class="flex items-center gap-3 mt-auto pt-3 border-t border-white/[0.04]">
            <div class="flex items-center gap-1.5">
              <button
                @click.prevent="toggleChat(kb)"
                class="relative w-8 h-4 rounded-full transition-all cursor-pointer border"
                :class="kb.is_enabled_chat ? 'bg-blue-500/20 border-blue-500/40' : 'bg-white/5 border-white/10'"
                :title="kb.is_enabled_chat ? 'Activo para Chat' : 'Inactivo para Chat'"
              >
                <div class="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full transition-all"
                  :class="kb.is_enabled_chat ? 'left-5 bg-blue-400' : 'left-1 bg-[#4a4a4a]'"
                ></div>
              </button>
              <span class="text-[9px] font-bold uppercase tracking-wider" :class="kb.is_enabled_chat ? 'text-blue-400' : 'text-[#4a4a4a]'">Chat</span>
            </div>
            <div class="flex items-center gap-1.5">
              <button
                @click.prevent="toggleReactive(kb)"
                class="relative w-8 h-4 rounded-full transition-all cursor-pointer border"
                :class="kb.is_enabled_reactive ? 'bg-emerald-500/20 border-emerald-500/40' : 'bg-white/5 border-white/10'"
                :title="kb.is_enabled_reactive ? 'Activo para Reactiva' : 'Inactivo para Reactiva'"
              >
                <div class="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full transition-all"
                  :class="kb.is_enabled_reactive ? 'left-5 bg-emerald-400' : 'left-1 bg-[#4a4a4a]'"
                ></div>
              </button>
              <span               class="text-[9px] font-bold uppercase tracking-wider" :class="kb.is_enabled_reactive ? 'text-emerald-400' : 'text-[#4a4a4a]'">Reactiva</span>
            </div>
          </div>
          
          <div class="text-[11px] text-[#7a7a7a] mt-2 font-bold uppercase tracking-widest flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><line x1="3" x2="21" y1="9" y2="9"/><line x1="9" x2="9" y1="21" y2="9"/></svg>
            {{ formatDate(kb.created_at) }}
          </div>
        </router-link>
      </div>
    </div>
  </div>

  <!-- Create Modal -->
  <Teleport to="body">
    <div v-if="showCreateModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center p-4 animate-in">
      <div 
        class="bg-[#1c1c1c] border border-white/[0.08] rounded-2xl w-full max-w-[420px] shadow-2xl p-6 relative overflow-hidden"
        @click.stop
      >
        <h3 class="text-lg font-semibold text-white mb-1">Crear nueva colección</h3>
        <p class="text-[13px] text-[#7a7a7a] mb-6">Agrupa tus documentos y recupéralos juntos</p>
        
        <div class="space-y-4 mb-6">
          <div>
            <label class="block text-[12px] font-medium text-[#b4b4b4] mb-1.5 ml-0.5">Nombre</label>
            <input
              v-model="newKb.name"
              type="text"
              placeholder="ej. Normas OSHA 2026"
              class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white text-[14px] focus:outline-none focus:border-white/20 transition-all placeholder:text-[#7a7a7a]"
              @keyup.enter="createKb"
              autofocus
            >
          </div>
          
          <div>
            <label class="block text-[12px] font-medium text-[#b4b4b4] mb-1.5 ml-0.5">Descripción <span class="text-[#7a7a7a]">(Opcional)</span></label>
            <textarea
              v-model="newKb.description"
              rows="3"
              placeholder="¿Qué tipos de documentos incluirá?"
              class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white text-[14px] focus:outline-none focus:border-white/20 transition-all placeholder:text-[#7a7a7a] resize-none"
            ></textarea>
          </div>

          <!-- Context Toggles in Create Modal -->
          <div class="space-y-3 pt-2">
            <label class="block text-[12px] font-medium text-[#b4b4b4] ml-0.5">Disponible en</label>
            <div class="flex items-center gap-4">
              <label class="flex items-center gap-2.5 cursor-pointer group">
                <div class="relative w-10 h-5 rounded-full transition-all border"
                  :class="newKb.is_enabled_chat ? 'bg-blue-500/20 border-blue-500/40' : 'bg-white/5 border-white/10'"
                >
                  <button 
                    @click="newKb.is_enabled_chat = !newKb.is_enabled_chat"
                    class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all"
                    :class="newKb.is_enabled_chat ? 'left-6 bg-blue-400' : 'left-1 bg-[#4a4a4a]'"
                  ></button>
                </div>
                <span class="text-[13px] text-[#b4b4b4] group-hover:text-white transition-colors">Chat</span>
              </label>
              <label class="flex items-center gap-2.5 cursor-pointer group">
                <div class="relative w-10 h-5 rounded-full transition-all border"
                  :class="newKb.is_enabled_reactive ? 'bg-emerald-500/20 border-emerald-500/40' : 'bg-white/5 border-white/10'"
                >
                  <button 
                    @click="newKb.is_enabled_reactive = !newKb.is_enabled_reactive"
                    class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all"
                    :class="newKb.is_enabled_reactive ? 'left-6 bg-emerald-400' : 'left-1 bg-[#4a4a4a]'"
                  ></button>
                </div>
                <span class="text-[13px] text-[#b4b4b4] group-hover:text-white transition-colors">Reactiva</span>
              </label>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3">
          <button 
            @click="showCreateModal = false"
            class="px-4 py-2 text-[14px] font-medium text-[#b4b4b4] hover:text-white hover:bg-white/5 rounded-xl transition-all"
          >
            Cancelar
          </button>
          <button
            @click="createKb"
            :disabled="!newKb.name.trim() || creating"
            class="px-6 py-2 text-[14px] font-medium bg-white/5 border border-white/10 text-white hover:bg-white/10 rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <svg v-if="creating" class="animate-spin h-4 w-4 text-black" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span v-else>Crear</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, inject } from 'vue'
import { knowledgeService, type KnowledgeBase } from '@/services/knowledgeService'

const collections = ref<KnowledgeBase[]>([])
const loading = ref(true)
const showCreateModal = ref(false)
const creating = ref(false)
const searchQuery = ref('')
const refreshKnowledgeBases = inject<() => void>('refreshKnowledgeBases', () => {})

const newKb = ref({
  name: '',
  description: '',
  is_enabled_chat: true,
  is_enabled_reactive: false
})

const filteredCollections = computed(() => {
  if (!searchQuery.value) return collections.value
  const query = searchQuery.value.toLowerCase()
  return collections.value.filter(c => 
    c.name.toLowerCase().includes(query) || 
    (c.description && c.description.toLowerCase().includes(query))
  )
})

async function fetchCollections() {
  try {
    loading.value = true
    collections.value = await knowledgeService.listKnowledgeBases()
  } catch (error) {
    console.error('Failed to fetch knowledge bases:', error)
  } finally {
    loading.value = false
  }
}

async function createKb() {
  if (!newKb.value.name.trim() || creating.value) return
  
  try {
    creating.value = true
    const created = await knowledgeService.createKnowledgeBase(
      newKb.value.name, 
      newKb.value.description,
      newKb.value.is_enabled_chat,
      newKb.value.is_enabled_reactive
    )
    collections.value.unshift(created)
    showCreateModal.value = false
    newKb.value = { name: '', description: '', is_enabled_chat: true, is_enabled_reactive: false }
    refreshKnowledgeBases()
  } catch (error) {
    console.error('Failed to create knowledge base:', error)
    alert('Error creating collection')
  } finally {
    creating.value = false
  }
}

async function deleteKb(id: string) {
  if (!confirm('Are you sure you want to delete this collection? All its documents will also be removed.')) return
  
  try {
    await knowledgeService.deleteKnowledgeBase(id)
    collections.value = collections.value.filter(c => c.id !== id)
    refreshKnowledgeBases()
  } catch (error) {
    console.error('Failed to delete kb:', error)
    alert('Error deleting collection')
  }
}

async function toggleChat(kb: KnowledgeBase) {
  try {
    await knowledgeService.toggleChat(kb.id, !kb.is_enabled_chat)
    kb.is_enabled_chat = !kb.is_enabled_chat
  } catch (error) {
    console.error('Failed to toggle chat:', error)
    alert('Error toggling chat context')
  }
}

async function toggleReactive(kb: KnowledgeBase) {
  try {
    await knowledgeService.toggleReactive(kb.id, !kb.is_enabled_reactive)
    kb.is_enabled_reactive = !kb.is_enabled_reactive
  } catch (error) {
    console.error('Failed to toggle reactive:', error)
    alert('Error toggling reactive context')
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
  fetchCollections()
})
</script>

<style scoped>
.animate-in {
  animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
