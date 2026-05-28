<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import promptService, { type Prompt, type PromptCreate } from '@/services/promptService'
import toolService, { type ToolConfig, type MCPSource } from '@/services/toolService'
import VariableAutocomplete from '@/components/common/VariableAutocomplete.vue'
import RichVariablesInput from '@/components/common/RichVariablesInput.vue'

const availableTools = ref<ToolConfig[]>([])
const availableSources = ref<MCPSource[]>([])
const cursorPos = ref(0)
const richInputRef = ref<InstanceType<typeof RichVariablesInput> | null>(null)

const prompts = ref<Prompt[]>([])
const isLoading = ref(true)
const isModalOpen = ref(false)
const isEditing = ref(false)
const currentPromptId = ref<string | null>(null)
const searchQuery = ref('')

const newPrompt = ref<PromptCreate>({
  title: '',
  description: '',
  query: '',
  icon: '',
  is_enabled: true
})

onMounted(async () => {
  await fetchPrompts()
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

function updateCursorPos(e: Event) {
  // Not needed linearly, rely on the component event
}

function handleVariableInsert(newQuery: string, newPos: number) {
  newPrompt.value.query = newQuery
  cursorPos.value = newPos
  setTimeout(() => {
    if (richInputRef.value) {
      richInputRef.value.focusAndSetCursor(newPos)
    }
  }, 20)
}

async function fetchPrompts() {
  try {
    isLoading.value = true
    prompts.value = await promptService.listPrompts()
  } catch (error) {
    console.error('Error fetching prompts:', error)
  } finally {
    isLoading.value = false
  }
}

function openCreateModal() {
  isEditing.value = false
  currentPromptId.value = null
  newPrompt.value = { title: '', description: '', query: '', icon: '', is_enabled: true }
  isModalOpen.value = true
}

function openEditModal(prompt: Prompt) {
  isEditing.value = true
  currentPromptId.value = prompt.id
  newPrompt.value = {
    title: prompt.title,
    description: prompt.description || '',
    query: prompt.query,
    icon: prompt.icon || '',
    is_enabled: prompt.is_enabled
  }
  isModalOpen.value = true
}

async function savePrompt() {
  try {
    if (isEditing.value && currentPromptId.value) {
      await promptService.updatePrompt(currentPromptId.value, newPrompt.value)
    } else {
      await promptService.createPrompt(newPrompt.value)
    }
    isModalOpen.value = false
    await fetchPrompts()
  } catch (error) {
    console.error('Error saving prompt:', error)
  }
}

async function togglePrompt(prompt: Prompt) {
  try {
    await promptService.updatePrompt(prompt.id, { is_enabled: !prompt.is_enabled })
    await fetchPrompts()
  } catch (error) {
    console.error('Error toggling prompt:', error)
  }
}

async function deletePrompt(id: string) {
  if (!confirm('Are you sure you want to delete this prompt?')) return
  try {
    await promptService.deletePrompt(id)
    await fetchPrompts()
  } catch (error) {
    console.error('Error deleting prompt:', error)
  }
}

const filteredPrompts = ref<Prompt[]>([])
// Simple reactive filter
watch([prompts, searchQuery], () => {
  if (!searchQuery.value) {
    filteredPrompts.value = prompts.value
  } else {
    const q = searchQuery.value.toLowerCase()
    filteredPrompts.value = prompts.value.filter(p => 
      p.title.toLowerCase().includes(q) || 
      (p.description && p.description.toLowerCase().includes(q))
    )
  }
}, { immediate: true })
</script>

<template>
  <div class="h-full flex flex-col pt-4 overflow-hidden">
    <!-- Header -->
    <div class="px-8 mb-6 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-3">
        <h2 class="text-xl font-semibold text-white">Prompts</h2>
        <span class="text-[14px] text-[#7a7a7a] font-medium">{{ prompts.length }}</span>
      </div>
      <button 
        @click="openCreateModal"
        class="bg-white text-black px-4 py-2 rounded-xl font-semibold hover:bg-gray-200 transition-colors flex items-center gap-2 text-[13px]"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
        New Prompt
      </button>
    </div>

    <!-- Search Section -->
    <div class="px-8 mb-6 shrink-0">
      <div class="relative group">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="absolute left-4 top-1/2 -translate-y-1/2 text-[#7a7a7a] group-focus-within:text-white transition-colors"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <div class="absolute left-11 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none">
          <button class="bg-[#2f2f2f] text-[11px] text-[#7a7a7a] px-2 py-0.5 rounded cursor-default border border-white/5 pointer-events-auto hover:text-white">All Prompts</button>
        </div>
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="Search Prompts" 
          class="w-full bg-[#2f2f2f]/30 border border-white/[0.06] rounded-xl pl-[112px] pr-4 py-3 text-[14px] text-[#ececec] placeholder-[#7a7a7a] focus:outline-none focus:border-white/10 focus:bg-[#2f2f2f]/50 transition-all"
        >
      </div>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-y-auto px-8 pb-12 custom-scrollbar">
      <!-- Loading -->
      <div v-if="isLoading" class="flex justify-center items-center py-20">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
      </div>

      <!-- Empty -->
      <div v-else-if="filteredPrompts.length === 0" class="flex flex-col items-center justify-center py-32 text-center">
        <div class="text-4xl mb-4">🧐</div>
        <h3 class="text-lg font-medium text-white mb-2">{{ searchQuery ? 'No results found' : 'No prompts found' }}</h3>
        <p class="text-[14px] text-[#7a7a7a] mb-8 max-w-sm">
          {{ searchQuery ? 'Try adjusting your search to find the prompt you need.' : 'Create your first prompt to help users get standard responses quickly.' }}
        </p>
        <button 
          v-if="!searchQuery"
          @click="openCreateModal"
          class="text-[13px] font-bold bg-white/5 hover:bg-white/10 text-white border border-white/10 px-6 py-2.5 rounded-xl transition-all"
        >
          New Prompt
        </button>
      </div>

      <!-- Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <div 
          v-for="prompt in filteredPrompts" 
          :key="prompt.id"
          class="p-5 bg-[#2f2f2f]/30 rounded-2xl border border-white/[0.06] hover:bg-[#2f2f2f]/50 hover:border-white/10 transition-all flex flex-col group relative h-48"
        >
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center gap-3">
            <div class="p-2 bg-[#212121] rounded-lg text-[#b4b4b4] border border-white/[0.06]" v-html="prompt.icon || '<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'16\' height=\'16\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><path d=\'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z\'/></svg>'"></div>
            <h3 class="font-medium text-white text-[14px]">{{ prompt.title }}</h3>
          </div>
          <button 
            @click="togglePrompt(prompt)"
            :class="prompt.is_enabled ? 'bg-green-500/15 text-green-400' : 'bg-white/5 text-[#7a7a7a]'"
            class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider"
          >
            {{ prompt.is_enabled ? 'On' : 'Off' }}
          </button>
        </div>
        <p class="text-[13px] text-[#7a7a7a] line-clamp-2 mb-4 flex-grow">{{ prompt.description }}</p>
        <div class="flex items-center justify-between border-t border-white/[0.06] pt-3">
          <div class="text-[10px] text-[#7a7a7a] font-mono truncate max-w-[120px]">
            {{ prompt.query }}
          </div>
          <div class="flex items-center gap-1">
            <button @click="openEditModal(prompt)" class="p-1.5 hover:bg-white/5 rounded-lg text-[#7a7a7a] hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            <button @click="deletePrompt(prompt.id)" class="p-1.5 hover:bg-red-500/10 rounded-lg text-[#7a7a7a] hover:text-red-400 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal -->
    <div v-if="isModalOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="isModalOpen = false"></div>
      <div class="bg-[#2f2f2f] border border-white/10 rounded-2xl w-full max-w-md relative z-10 overflow-hidden shadow-2xl">
        <div class="p-6 border-b border-white/[0.06]">
          <h2 class="text-lg font-semibold text-white">{{ isEditing ? 'Edit Prompt' : 'New Prompt' }}</h2>
        </div>
        <div class="p-6 space-y-4">
          <div>
            <label class="block text-[12px] font-medium text-[#7a7a7a] mb-1.5 ml-0.5">Title</label>
            <input 
              v-model="newPrompt.title"
              type="text" 
              placeholder="e.g. Summarize document"
              class="w-full bg-[#212121] border border-white/[0.08] rounded-xl px-4 py-2.5 text-[14px] text-white focus:outline-none focus:border-white/20 transition-all placeholder:text-[#7a7a7a]"
            >
          </div>
          <div>
            <label class="block text-[12px] font-medium text-[#7a7a7a] mb-1.5 ml-0.5">Description</label>
            <textarea 
              v-model="newPrompt.description"
              placeholder="Brief explanation of what the prompt does"
              class="w-full bg-[#212121] border border-white/[0.08] rounded-xl px-4 py-2.5 text-[14px] text-white focus:outline-none focus:border-white/20 transition-all placeholder:text-[#7a7a7a] h-20 resize-none"
            ></textarea>
          </div>
          <div>
            <label class="block text-[12px] font-medium text-[#7a7a7a] mb-1.5 ml-0.5">Query (LLM Question)</label>
            <div class="relative">
              <VariableAutocomplete 
                :sources="availableSources"
                :tools="availableTools" 
                :query="newPrompt.query" 
                :cursorPosition="cursorPos" 
                @insert="handleVariableInsert" 
                @close="cursorPos = 0" 
              />
              <RichVariablesInput 
                ref="richInputRef"
                id="prompt-query-input"
                v-model="newPrompt.query"
                @cursor-update="cursorPos = $event"
                placeholder="e.g. Make a detailed summary of this PDF"
                class="w-full bg-[#212121] border border-white/[0.08] rounded-xl px-4 py-2.5 text-[14px] text-white focus:outline-none focus:border-white/20 transition-all placeholder:text-[#7a7a7a] min-h-[44px]"
              />
            </div>
          </div>
        </div>
        <div class="p-6 bg-white/[0.02] flex items-center justify-end gap-3">
          <button @click="isModalOpen = false" class="px-4 py-2 text-[14px] font-medium text-[#b4b4b4] hover:text-white transition-colors">Cancel</button>
          <button @click="savePrompt" class="px-6 py-2 bg-white text-black rounded-xl text-[13px] font-semibold hover:bg-gray-200 transition-colors">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>
