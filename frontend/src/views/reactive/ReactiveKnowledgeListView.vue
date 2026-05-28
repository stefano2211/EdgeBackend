<template>
  <div class="h-full flex flex-col pt-6 overflow-hidden bg-[#0a0a0a]">
    <!-- Header Section -->
    <header class="px-8 mb-8 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-4">
        <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/5">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
        </div>
        <div>
          <h2 class="text-2xl font-bold text-white tracking-tight">Knowledge</h2>
          <p class="text-[13px] text-[#7a7a7a] font-medium mt-0.5">Manage knowledge bases for chat and reactive pipelines.</p>
        </div>
      </div>

      <button 
        @click="showCreateModal = true"
        class="flex items-center gap-2 bg-white/5 hover:bg-white/10 text-white border border-white/10 font-semibold px-5 py-2.5 rounded-xl transition-all shrink-0 text-[13px]"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
        Create Collection
      </button>
    </header>

    <!-- Search & Stats Bar -->
    <div class="px-8 mb-8 shrink-0 flex items-center gap-4">
      <div class="relative flex-1 group">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="absolute left-4 top-1/2 -translate-y-1/2 text-[#4a4a4a] group-focus-within:text-emerald-400 transition-colors"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="Filter collections..." 
          class="w-full bg-[#1a1a1a]/50 border border-white/[0.05] rounded-2xl pl-12 pr-4 py-3.5 text-[14px] text-[#ececec] placeholder-[#4a4a4a] focus:outline-none focus:border-emerald-500/30 focus:bg-[#1a1a1a] transition-all backdrop-blur-sm"
        >
      </div>
      <div class="hidden md:flex items-center gap-2 px-4 py-3.5 bg-white/[0.02] border border-white/[0.05] rounded-2xl">
        <span class="text-[11px] font-bold text-[#4a4a4a] uppercase tracking-widest">Active for Reactive:</span>
        <span class="text-[13px] font-mono text-emerald-400">{{ activeCount }}</span>
      </div>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-y-auto px-8 pb-12 custom-scrollbar">
      <!-- Loading State -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <div v-for="i in 8" :key="i" class="bg-white/[0.02] border border-white/[0.05] rounded-3xl h-56 animate-pulse flex flex-col p-6 space-y-4">
          <div class="w-12 h-12 bg-white/5 rounded-xl"></div>
          <div class="h-6 bg-white/5 rounded-lg w-3/4"></div>
          <div class="h-4 bg-white/5 rounded-lg w-full"></div>
          <div class="h-4 bg-white/5 rounded-lg w-1/2 mt-auto"></div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredCollections.length === 0" class="flex flex-col items-center justify-center py-32 text-center max-w-lg mx-auto">
        <div class="w-24 h-24 rounded-full bg-emerald-500/5 border border-emerald-500/10 flex items-center justify-center mb-6 animate-float">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-500/20"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/><path d="M8 7h6"/><path d="M8 11h8"/><path d="M8 15h6"/></svg>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">{{ searchQuery ? 'No matching collections' : 'No Knowledge Bases' }}</h3>
        <p class="text-[14px] text-[#7a7a7a] mb-8 leading-relaxed">
          {{ searchQuery ? 'Try adjusting your search criteria.' : 'Create your first knowledge collection to group documents and use them in chat or reactive pipelines.' }}
        </p>
        <button 
          v-if="!searchQuery"
          @click="showCreateModal = true"
          class="text-[13px] font-bold bg-white text-black px-8 py-3 rounded-xl transition-all hover:scale-105 active:scale-95 shadow-xl shadow-white/5"
        >
          Create Collection
        </button>
      </div>

      <!-- Grid Content -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <div
          v-for="kb in filteredCollections"
          :key="kb.id"
          class="group bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.05] hover:border-emerald-500/30 rounded-3xl p-6 transition-all cursor-pointer relative flex flex-col h-56 overflow-hidden backdrop-blur-sm"
        >
          <!-- Hover Glow -->
          <div class="absolute -right-12 -top-12 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl group-hover:bg-emerald-500/15 transition-all duration-500"></div>

          <div class="flex items-start justify-between mb-4 relative z-10">
            <router-link 
              :to="{ name: 'reactive-knowledge-detail', params: { id: kb.id } }"
              class="w-12 h-12 rounded-2xl bg-[#141414] flex items-center justify-center border border-white/[0.05] hover:border-emerald-500/20 hover:text-emerald-400 transition-all duration-300"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#4a4a4a] group-hover:text-emerald-400 transition-colors"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>
            </router-link>
            <button @click="deleteKb(kb.id)" class="text-[#7a7a7a] hover:text-red-400 p-1.5 hover:bg-white/10 rounded-lg opacity-0 group-hover:opacity-100 transition-all">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            </button>
          </div>
          
          <router-link 
            :to="{ name: 'reactive-knowledge-detail', params: { id: kb.id } }"
            class="relative z-10"
          >
            <h3 class="font-bold text-[17px] text-white mb-1 leading-tight truncate tracking-tight group-hover:text-emerald-400 transition-colors">{{ kb.name }}</h3>
            <p class="text-[#7a7a7a] text-[13px] line-clamp-2 mb-4 flex-grow leading-relaxed">{{ kb.description || 'No description provided.' }}</p>
          </router-link>
          
          <!-- Context Toggles -->
          <div class="flex items-center gap-3 mt-auto pt-4 border-t border-white/[0.03] relative z-10">
            <div class="flex items-center gap-1.5">
              <button
                @click="toggleChat(kb)"
                class="relative w-8 h-4 rounded-full transition-all cursor-pointer border"
                :class="kb.is_enabled_chat ? 'bg-blue-500/20 border-blue-500/40' : 'bg-white/5 border-white/10'"
                :title="kb.is_enabled_chat ? 'Active for Chat' : 'Inactive for Chat'"
              >
                <div class="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full transition-all"
                  :class="kb.is_enabled_chat ? 'left-5 bg-blue-400' : 'left-1 bg-[#4a4a4a]'"
                ></div>
              </button>
              <span class="text-[9px] font-bold uppercase tracking-wider" :class="kb.is_enabled_chat ? 'text-blue-400' : 'text-[#4a4a4a]'">Chat</span>
            </div>
            <div class="flex items-center gap-1.5">
              <button
                @click="toggleReactive(kb)"
                class="relative w-8 h-4 rounded-full transition-all cursor-pointer border"
                :class="kb.is_enabled_reactive ? 'bg-emerald-500/20 border-emerald-500/40' : 'bg-white/5 border-white/10'"
                :title="kb.is_enabled_reactive ? 'Active for Reactive' : 'Inactive for Reactive'"
              >
                <div class="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full transition-all"
                  :class="kb.is_enabled_reactive ? 'left-5 bg-emerald-400' : 'left-1 bg-[#4a4a4a]'"
                ></div>
              </button>
              <span class="text-[9px] font-bold uppercase tracking-wider" :class="kb.is_enabled_reactive ? 'text-emerald-400' : 'text-[#4a4a4a]'">Reactive</span>
            </div>
          </div>
        </div>
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
        <h3 class="text-lg font-semibold text-white mb-1">Create new collection</h3>
        <p class="text-[13px] text-[#7a7a7a] mb-6">Group your documents and retrieve them together</p>
        
        <div class="space-y-4 mb-6">
          <div>
            <label class="block text-[12px] font-medium text-[#b4b4b4] mb-1.5 ml-0.5">Name</label>
            <input
              v-model="newKb.name"
              type="text"
              placeholder="e.g. OSHA Regulations 2026"
              class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white text-[14px] focus:outline-none focus:border-white/20 transition-all placeholder:text-[#7a7a7a]"
              @keyup.enter="createKb"
              autofocus
            >
          </div>
          
          <div>
            <label class="block text-[12px] font-medium text-[#b4b4b4] mb-1.5 ml-0.5">Description <span class="text-[#7a7a7a]">(Optional)</span></label>
            <textarea
              v-model="newKb.description"
              rows="3"
              placeholder="What types of documents will this include?"
              class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white text-[14px] focus:outline-none focus:border-white/20 transition-all placeholder:text-[#7a7a7a] resize-none"
            ></textarea>
          </div>

          <!-- Context Toggles in Create Modal -->
          <div class="space-y-3 pt-2">
            <label class="block text-[12px] font-medium text-[#b4b4b4] ml-0.5">Available In</label>
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
                <span class="text-[13px] text-[#b4b4b4] group-hover:text-white transition-colors">Reactive</span>
              </label>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3">
          <button 
            @click="showCreateModal = false"
            class="px-4 py-2 text-[14px] font-medium text-[#b4b4b4] hover:text-white hover:bg-white/5 rounded-xl transition-all"
          >
            Cancel
          </button>
          <button
            @click="createKb"
            :disabled="!newKb.name.trim() || creating"
            class="px-6 py-2 text-[14px] font-medium bg-white/5 border border-white/10 text-white hover:bg-white/10 rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <svg v-if="creating" class="animate-spin h-4 w-4 text-black" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span v-else>Create</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { knowledgeService, type KnowledgeBase } from '@/services/knowledgeService'

const collections = ref<KnowledgeBase[]>([])
const loading = ref(true)
const showCreateModal = ref(false)
const creating = ref(false)
const searchQuery = ref('')
const togglingId = ref<string | null>(null)

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

const activeCount = computed(() => collections.value.filter(k => k.is_enabled_reactive).length)

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
  } catch (error) {
    console.error('Failed to delete kb:', error)
    alert('Error deleting collection')
  }
}

async function toggleChat(kb: KnowledgeBase) {
  if (togglingId.value !== null) return
  
  const originalStatus = kb.is_enabled_chat
  try {
    togglingId.value = kb.id
    kb.is_enabled_chat = !kb.is_enabled_chat
    await knowledgeService.toggleChat(kb.id, kb.is_enabled_chat)
  } catch (error) {
    console.error('Failed to toggle chat:', error)
    kb.is_enabled_chat = originalStatus
    alert('Error toggling chat context')
  } finally {
    togglingId.value = null
  }
}

async function toggleReactive(kb: KnowledgeBase) {
  if (togglingId.value !== null) return
  
  const originalStatus = kb.is_enabled_reactive
  try {
    togglingId.value = kb.id
    kb.is_enabled_reactive = !kb.is_enabled_reactive
    await knowledgeService.toggleReactive(kb.id, kb.is_enabled_reactive)
  } catch (error) {
    console.error('Failed to toggle reactive:', error)
    kb.is_enabled_reactive = originalStatus
    alert('Error toggling reactive context')
  } finally {
    togglingId.value = null
  }
}

onMounted(() => {
  fetchCollections()
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

.animate-in {
  animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
