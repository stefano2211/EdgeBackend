<script setup lang="ts">
import { ref, onMounted, onUnmounted, provide, reactive } from 'vue'
import { useRouter } from 'vue-router'
import Sidebar from '@/components/layout/Sidebar.vue'
import ChatControls from '@/components/chat/ChatControls.vue'
import { conversationService, type Conversation, type MessageItem } from '@/services/conversationService'
import { knowledgeService, type KnowledgeBase } from '@/services/knowledgeService'
import modelService from '@/services/modelService'
import toolService, { type MCPSource } from '@/services/toolService'
import api from '@/services/api'
import { authService } from '@/services/authService'
import { systemService } from '@/services/systemService'
import eventService from '@/services/eventService'
import { databaseService, type DatabaseConnection } from '@/services/databaseService'

const router = useRouter()
const isSidebarOpen = ref(true)
const pendingEventsCount = ref(0)
let pendingEventsPollTimer: ReturnType<typeof setInterval> | null = null
const isControlsOpen = ref(false)
const isHeaderMenuOpen = ref(false)

// User state
const userName = ref('')

// Model state
const orchestratorModel = ref('Cargando...')
const activeUsers = ref(1)
const showArchivedModal = ref(false)
const archivedConversations = ref<Conversation[]>([])
const isLoadingArchived = ref(false)

// Models state
const availableModels = ref<any[]>([])
const activeModelId = ref<string | undefined>(undefined)
const activeModelName = ref('Select Model')
const showModelDropdown = ref(false)

// Chat params (controlled by ChatControls drawer)
const chatParams = reactive({
  system_prompt: '',
  temperature: null as number | null,
  max_tokens: null as number | null,
  top_p: null as number | null,
  top_k: null as number | null,
  seed: null as number | null,
  stop_sequence: ''
})

// Conversation state
const conversations = ref<Conversation[]>([])
const activeThreadId = ref<string | null>(null)
const activeMessages = ref<MessageItem[]>([])
const isLoadingMessages = ref(false)

// Knowledge bases 
const knowledgeBases = ref<KnowledgeBase[]>([])
const activeKnowledgeBaseId = ref<string | null>(null)
const showKbDropdown = ref(false)

// MCP Sources
const mcpSources = ref<MCPSource[]>([])
const activeMcpSourceId = ref<string | null>(null)

// Database Connections
const databaseConnections = ref<DatabaseConnection[]>([])
const activeDbConnectionIds = ref<string[]>([])

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
}

async function pollPendingEvents() {
  try {
    const res = await eventService.listEvents({ status: 'awaiting_approval', limit: 1 })
    pendingEventsCount.value = res.total
  } catch {}
}

// Load user info
async function loadUserInfo() {
  try {
    const response = await api.get('/api/v1/auth/me')
    userName.value = response.data.username || response.data.email?.split('@')[0] || 'User'
  } catch (error) {
    console.error('Failed to load user info', error)
    userName.value = 'User'
  }
}

// Load model info
async function loadModelInfo() {
  try {
    const models = await modelService.listModels()
    availableModels.value = models
    
    // Try to find a default (first one or orchestrator)
    if (models.length > 0 && !activeModelId.value) {
      const orchestrator = models.find(m => m.id === 'orchestrator' || m.name.toLowerCase().includes('orchestrator'))
      const defaultModel = orchestrator || models[0]
      if (defaultModel) {
        activeModelId.value = defaultModel.id
        activeModelName.value = defaultModel.name
      }
    } else if (models.length > 0 && activeModelId.value) {
      // Sync activeModelName if activeModelId is already set
      const current = models.find(m => m.id === activeModelId.value)
      if (current) {
        activeModelName.value = current.name
      }
    }
  } catch (error) {
    console.error('Failed to load model info', error)
    if (availableModels.value.length === 0) {
      activeModelName.value = 'Error'
    }
  }
}

async function toggleModelDropdown() {
  showModelDropdown.value = !showModelDropdown.value
  if (showModelDropdown.value) {
    await loadModelInfo()
  }
}

function selectModel(model: any) {
  activeModelId.value = model.id
  activeModelName.value = model.name
  showModelDropdown.value = false
}

async function loadStats() {
  try {
    const stats = await systemService.getStats()
    activeUsers.value = stats.active_users
  } catch (error) {
    console.error('Failed to load stats', error)
  }
}

async function handleOpenArchived() {
  isHeaderMenuOpen.value = false
  showArchivedModal.value = true
  isLoadingArchived.value = true
  try {
    archivedConversations.value = await conversationService.listArchived()
  } catch (error) {
    console.error('Failed to load archived conversations', error)
  } finally {
    isLoadingArchived.value = false
  }
}

async function handleUnarchive(threadId: string) {
  try {
    await conversationService.archive(threadId, false)
    archivedConversations.value = archivedConversations.value.filter(c => c.thread_id !== threadId)
    loadConversations()
  } catch (error) {
    console.error('Failed to unarchive', error)
  }
}

// Load conversations from backend
async function loadConversations() {
  try {
    conversations.value = await conversationService.list()
  } catch (error) {
    console.error('Failed to load conversations', error)
  }
}

async function loadKnowledgeBases() {
  try {
    knowledgeBases.value = await knowledgeService.listKnowledgeBases()
    if (activeKnowledgeBaseId.value && !knowledgeBases.value.find(kb => kb.id === activeKnowledgeBaseId.value)) {
      activeKnowledgeBaseId.value = null
    }
  } catch (error) {
    console.error('Failed to load knowledge bases', error)
  }
}

async function loadMcpSources() {
  try {
    mcpSources.value = await toolService.listSources()
    if (activeMcpSourceId.value && !mcpSources.value.find(s => s.id === activeMcpSourceId.value)) {
      activeMcpSourceId.value = null
    }
  } catch (error) {
    console.error('Failed to load MCP sources', error)
  }
}

function selectMcpSource(id: string | null) {
  activeMcpSourceId.value = id
}

async function loadDatabaseConnections() {
  try {
    databaseConnections.value = await databaseService.listConnections('chat')
    // Filter out any active IDs that no longer exist or are no longer available
    activeDbConnectionIds.value = activeDbConnectionIds.value.filter(
      id => databaseConnections.value.find(c => c.id === id && c.available_in_chat)
    )
  } catch (error) {
    console.error('Failed to load database connections', error)
  }
}

function selectDbConnection(id: string) {
  const idx = activeDbConnectionIds.value.indexOf(id)
  if (idx >= 0) {
    activeDbConnectionIds.value.splice(idx, 1)
  } else {
    activeDbConnectionIds.value.push(id)
  }
}

function setAllDbConnections(enabled: boolean) {
  if (enabled) {
    activeDbConnectionIds.value = databaseConnections.value
      .filter(c => c.available_in_chat)
      .map(c => c.id)
  } else {
    activeDbConnectionIds.value = []
  }
}

function selectKb(id: string | null) {
  activeKnowledgeBaseId.value = id
  showKbDropdown.value = false
}

// Create a new chat
async function handleNewChat() {
  activeThreadId.value = null
  activeMessages.value = []
  if (router.currentRoute.value.path !== '/chat') {
    router.push('/chat')
  }
}

// Select an existing conversation
async function handleSelectConversation(threadId: string) {
  activeThreadId.value = threadId
  isLoadingMessages.value = true
  
  if (router.currentRoute.value.path !== '/chat') {
    router.push('/chat')
  }

  try {
    activeMessages.value = await conversationService.getMessages(threadId)
  } catch (error) {
    console.error('Failed to load messages', error)
    activeMessages.value = []
  } finally {
    isLoadingMessages.value = false
  }
}

// Handle logout
async function handleLogout() {
  await authService.logout()
  localStorage.removeItem('token')
  router.push('/login')
}

async function handleArchiveConversation(threadId: string) {
  try {
    await conversationService.archive(threadId)
    // Refresh conversations but stay on current page
    loadConversations()
    // If we're archiving the active thread, we might want to go to a new chat
    if (activeThreadId.value === threadId) {
      handleNewChat()
    }
  } catch (error) {
    console.error('Failed to archive conversation', error)
  }
}

// Called by ChatView after sending a message
function handleMessageSent(threadId: string, _userMsg: MessageItem, _assistantMsg: MessageItem) {
  if (!activeThreadId.value) {
    activeThreadId.value = threadId
  }
  loadConversations()
}

// Provide state to child components
provide('activeThreadId', activeThreadId)
provide('activeModelId', activeModelId)
provide('activeMessages', activeMessages)
provide('isLoadingMessages', isLoadingMessages)
provide('onMessageSent', handleMessageSent)
provide('activeKnowledgeBaseId', activeKnowledgeBaseId)
provide('knowledgeBases', knowledgeBases)
provide('refreshKnowledgeBases', loadKnowledgeBases)
provide('showKbDropdown', showKbDropdown)
provide('selectKb', selectKb)

provide('activeMcpSourceId', activeMcpSourceId)
provide('mcpSources', mcpSources)
provide('selectMcpSource', selectMcpSource)
provide('refreshMcpSources', loadMcpSources)
provide('userName', userName)
provide('chatParams', chatParams)

provide('databaseConnections', databaseConnections)
provide('activeDbConnectionIds', activeDbConnectionIds)
provide('selectDbConnection', selectDbConnection)
provide('setAllDbConnections', setAllDbConnections)
provide('refreshDatabaseConnections', loadDatabaseConnections)

onMounted(() => {
  loadUserInfo()
  loadConversations()
  loadKnowledgeBases()
  loadMcpSources()
  loadDatabaseConnections()
  loadModelInfo()
  loadStats()
  pollPendingEvents()
  setInterval(loadStats, 60000)
  pendingEventsPollTimer = setInterval(pollPendingEvents, 30000)
})

onUnmounted(() => {
  if (pendingEventsPollTimer) clearInterval(pendingEventsPollTimer)
})
</script>

<template>
  <div class="h-screen w-screen bg-[#0a0a0a] text-white flex overflow-hidden">
    <!-- Left Sidebar -->
    <Sidebar
      :is-open="isSidebarOpen"
      :conversations="conversations"
      :active-thread-id="activeThreadId"
      :user-name="userName"
      :pending-events="pendingEventsCount"
      @toggle="toggleSidebar"
      @new-chat="handleNewChat"
      @select-conversation="handleSelectConversation"
      @logout="handleLogout"
      @archive-action="handleOpenArchived"
    />

    <!-- Main Content Area Wrapper -->
    <main class="flex-1 flex flex-col relative bg-[#0a0a0a] min-w-0">
      <!-- Top header -->
      <header class="h-14 shrink-0 flex items-center justify-between px-5 sticky top-0 w-full z-10 bg-[#0a0a0a] border-b border-white/[0.06]">
        <!-- Left: breadcrumb -->
        <div class="flex items-center gap-2 text-[13px]">
          <span class="text-[#555] font-medium">Aura AI</span>
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#333]"><path d="m9 18 6-6-6-6"/></svg>
          <span class="text-[#b4b4b4] font-medium">Chat</span>
        </div>

        <!-- Right: model + user -->
        <div class="flex items-center gap-3">
          <!-- Model Selector -->
          <button
            @click="toggleModelDropdown"
            class="flex items-center gap-2 px-2.5 py-1 rounded-lg text-[12px] font-medium border border-white/[0.06] hover:border-white/10 transition-all"
            :class="showModelDropdown ? 'bg-white/[0.04] text-white' : 'text-[#7a7a7a] hover:text-[#b4b4b4]'"
          >
            <div class="w-1.5 h-1.5 rounded-full" :class="availableModels.length > 0 ? 'bg-emerald-400' : 'bg-red-400'"></div>
            <span class="truncate max-w-[120px]">{{ activeModelName }}</span>
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
          </button>

          <!-- Model Selector Dropdown -->
          <Teleport to="body">
            <Transition name="dropdown">
              <div v-if="showModelDropdown" class="fixed top-14 left-auto right-20 w-64 bg-[#1c1c1c] rounded-xl shadow-2xl border border-white/[0.08] z-[10000] overflow-hidden">
                <div class="p-2 space-y-1 max-h-[400px] overflow-y-auto">
                  <div class="px-3 py-1.5 text-[11px] font-semibold text-[#555] uppercase tracking-wider">Available Models</div>
                  <button
                    v-for="model in availableModels"
                    :key="model.id"
                    @click="selectModel(model)"
                    class="group w-full text-left px-2.5 py-2 rounded-lg text-[12px] transition-colors truncate"
                    :class="activeModelId === model.id ? 'bg-white/[0.06] text-white font-medium' : 'text-[#888] hover:text-white hover:bg-white/[0.04]'"
                  >
                    <div class="w-2 h-2 rounded-full inline-block mr-2" :class="activeModelId === model.id ? 'bg-emerald-400' : 'bg-[#555]'"></div>
                    <span class="truncate">{{ model.name }}</span>
                  </button>
                </div>
              </div>
            </Transition>
          </Teleport>
        </div>

        <!-- Right: controls icons -->
        <div class="flex items-center gap-1">
          <!-- Dots menu -->
          <button class="p-2 text-[#7a7a7a] hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
          </button>
          <!-- Controls (sliders icon) -->
          <button
            @click="isControlsOpen = !isControlsOpen"
            class="p-2 hover:bg-white/5 rounded-lg transition-colors"
            :class="isControlsOpen ? 'text-white bg-white/5' : 'text-[#7a7a7a] hover:text-white'"
            title="Model Controls"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/></svg>
          </button>
          <!-- User avatar with dropdown -->
          <div class="relative ml-1">
            <button
              @click="isHeaderMenuOpen = !isHeaderMenuOpen"
              class="w-8 h-8 rounded-full bg-[#7a7a7a]/30 flex items-center justify-center hover:bg-white/10 transition-colors cursor-pointer"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </button>

            <!-- Dropdown menu -->
            <Teleport to="body">
              <Transition name="dropdown">
                <div v-if="isHeaderMenuOpen" class="fixed top-14 right-4 w-64 bg-[#2f2f2f] rounded-2xl shadow-2xl border border-white/[0.08] z-[10000]">
                  <div class="py-1.5">
                    <button @click="isHeaderMenuOpen = false; router.push('/admin/settings')" class="flex items-center gap-3 w-full px-4 py-2.5 text-[13px] text-[#ececec] hover:bg-white/5 transition-colors">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
                      Settings
                    </button>
                    <button @click="handleOpenArchived" class="flex items-center gap-3 w-full px-4 py-2.5 text-[13px] text-[#ececec] hover:bg-white/5 transition-colors">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>
                      Archived Chats
                    </button>
                    <button @click="isHeaderMenuOpen = false; router.push('/admin/users')" class="flex items-center gap-3 w-full px-4 py-2.5 text-[13px] text-[#ececec] hover:bg-white/5 transition-colors">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                      Admin Panel
                    </button>
                  </div>
                  <div class="border-t border-white/[0.06] py-1.5">
                    <button @click="isHeaderMenuOpen = false; handleLogout()" class="flex items-center gap-3 w-full px-4 py-2.5 text-[13px] text-[#ececec] hover:bg-white/5 transition-colors">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16,17 21,12 16,7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
                      Sign Out
                    </button>
                  </div>
                  <div class="border-t border-white/[0.06] px-4 py-2.5">
                    <div class="flex items-center gap-2 text-[12px] text-[#7a7a7a]">
                      <div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      Active Users: {{ activeUsers }}
                    </div>
                  </div>
                </div>
              </Transition>
            </Teleport>
          </div>
        </div>
      </header>

      <!-- Injected Child Route Content -->
      <div class="flex-1 flex flex-col w-full h-full">
        <RouterView />
      </div>
    </main>

    <!-- Controls Drawer -->
    <ChatControls
      :is-open="isControlsOpen"
      :params="chatParams"
      @close="isControlsOpen = false"
    />

    <!-- Click outside to close header dropdowns -->
    <Teleport to="body">
      <div v-if="isHeaderMenuOpen || showModelDropdown" class="fixed inset-0 z-30" @click="isHeaderMenuOpen = false; showModelDropdown = false"></div>
    </Teleport>

    <!-- Archived Chats Modal -->
    <Teleport to="body">
      <div v-if="showArchivedModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center p-4">
        <div class="bg-[#2f2f2f] border border-white/10 rounded-2xl w-full max-w-md shadow-2xl p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-lg font-semibold text-white">Archived Chats</h3>
            <button @click="showArchivedModal = false" class="text-[#7a7a7a] hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>

          <div class="space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar pr-2">
            <div v-if="isLoadingArchived" class="py-12 flex justify-center">
              <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-white"></div>
            </div>
            <div v-else-if="archivedConversations.length === 0" class="py-12 text-center text-[#7a7a7a]">
              No archived chats found.
            </div>
            <div
              v-for="conv in archivedConversations"
              :key="conv.thread_id"
              class="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/[0.05] hover:border-white/10 transition-all group"
            >
              <div class="truncate mr-4">
                <div class="text-[14px] font-medium truncate">{{ conv.title }}</div>
                <div class="text-[11px] text-[#555]">{{ new Date(conv.updated_at).toLocaleDateString() }}</div>
              </div>
              <button
                @click="handleUnarchive(conv.thread_id)"
                class="shrink-0 p-2 text-[#7a7a7a] hover:text-white hover:bg-white/5 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                title="Unarchive"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 12 2 2 4-4"/><rect width="18" height="18" x="3" y="3" rx="2"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.dropdown-enter-active { transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1); }
.dropdown-leave-active { transition: all 0.1s ease-in; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px) scale(0.95); }
</style>
