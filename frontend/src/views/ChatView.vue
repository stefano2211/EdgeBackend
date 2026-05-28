<script setup lang="ts">
import { inject, ref, watch, nextTick, type Ref } from 'vue'
import WelcomeState from '@/components/chat/WelcomeState.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
import ReasoningBlock from '@/components/chat/ReasoningBlock.vue'
import { chatService } from '@/services/chatService'
import type { MessageItem } from '@/services/conversationService'

// Injected from MainLayout
const activeThreadId = inject<Ref<string | null>>('activeThreadId', ref(null))
const activeKnowledgeBaseId = inject<Ref<string | null>>('activeKnowledgeBaseId', ref(null))
const activeModelId = inject<Ref<string | undefined>>('activeModelId', ref(undefined))
const activeMessages = inject<Ref<MessageItem[]>>('activeMessages', ref([]))
const isLoadingMessages = inject<Ref<boolean>>('isLoadingMessages', ref(false))
const activeMcpSourceId = inject<Ref<string | null>>('activeMcpSourceId', ref(null))
const onMessageSent = inject<(threadId: string, userMsg: MessageItem, assistantMsg: MessageItem) => void>('onMessageSent', () => {})
const chatParams = inject<any>('chatParams', {})

const isLoading = ref(false)
const streamingContent = ref('')
const streamingReasoning = ref('')
const chatContainer = ref<HTMLDivElement | null>(null)
const useGeneralist = ref(true)

interface SubagentStatus {
  name: string
  status: 'running' | 'complete' | 'error'
  input?: any
}
const activeSubagents = ref<SubagentStatus[]>([])

interface ClickPos { x: number; y: number; type: string }
interface ScreenshotFrame {
  b64: string
  step: number
  has_omniparser: boolean
  action?: string | null
  click?: ClickPos | null
}
const currentScreenshot = ref<ScreenshotFrame | null>(null)
const showScreenViewer = ref(false)
const isThinking = ref(false)
const clickRipple = ref<ClickPos | null>(null)
let _thinkingTimer: ReturnType<typeof setTimeout> | null = null
let _rippleTimer: ReturnType<typeof setTimeout> | null = null

// Human-in-the-loop state
const takeoverState = ref<{ message: string, thread_id: string, action_type: string } | null>(null)
const takeoverResponse = ref('')
const isResuming = ref(false)

// Takeover overlay dentro del panel (no inline)
// (takeoverState, takeoverResponse, isResuming ya definidos arriba)

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// Auto-scroll when messages change
watch(() => activeMessages.value.length, () => {
  scrollToBottom()
})

// Auto-scroll during streaming
watch(streamingContent, () => {
  scrollToBottom()
})

async function handleSendMessage(content: string) {
  // Add user message
  activeMessages.value.push({ role: 'user', content })
  isLoading.value = true
  streamingContent.value = ''
  streamingReasoning.value = ''
  activeSubagents.value = []
  currentScreenshot.value = null
  showScreenViewer.value = false
  isThinking.value = false
  clickRipple.value = null
  takeoverState.value = null
  takeoverResponse.value = ''
  if (_thinkingTimer) { clearTimeout(_thinkingTimer); _thinkingTimer = null }
  if (_rippleTimer)   { clearTimeout(_rippleTimer);   _rippleTimer   = null }
  scrollToBottom()

  try {
    // Build params object, omitting null/empty values
    const params: Record<string, any> = {}
    if (chatParams.system_prompt) params.system_prompt = chatParams.system_prompt
    if (chatParams.temperature !== null) params.temperature = chatParams.temperature
    if (chatParams.max_tokens !== null) params.max_tokens = chatParams.max_tokens
    if (chatParams.top_p !== null) params.top_p = chatParams.top_p
    if (chatParams.top_k !== null) params.top_k = chatParams.top_k
    if (chatParams.seed !== null) params.seed = chatParams.seed
    if (chatParams.stop_sequence) params.stop_sequence = chatParams.stop_sequence

    await chatService.sendMessageStream(
      content,
      activeThreadId.value || undefined,
      activeKnowledgeBaseId.value || undefined,
      activeMcpSourceId.value || undefined,
      activeModelId.value,
      Object.keys(params).length > 0 ? params : undefined,
      // onToken
      (token: string) => {
        streamingContent.value += token
      },
      // onMeta
      (meta: { thread_id: string }) => {
        if (!activeThreadId.value) {
          activeThreadId.value = meta.thread_id
        }
      },
      // onDone
      (fullContent: string) => {
        const assistantMsg: MessageItem = {
          role: 'assistant',
          content: fullContent,
          reasoning_content: streamingReasoning.value || null,
        }
        activeMessages.value.push(assistantMsg)
        streamingContent.value = ''
        streamingReasoning.value = ''
        isLoading.value = false
        isThinking.value = false
        if (_thinkingTimer) { clearTimeout(_thinkingTimer); _thinkingTimer = null }

        const threadId = activeThreadId.value || 'unknown'
        onMessageSent(threadId, { role: 'user', content }, assistantMsg)
      },
      // onError
      (error: string) => {
        const errMsg = streamingContent.value 
          ? streamingContent.value 
          : `Error: ${error}`
        activeMessages.value.push({ role: 'assistant', content: errMsg })
        streamingContent.value = ''
        activeSubagents.value = []
        isLoading.value = false
        isThinking.value = false
        if (_thinkingTimer) { clearTimeout(_thinkingTimer); _thinkingTimer = null }
        // Keep viewer open on error so user can see last known state
      },
      // onSubagent
      (subagent: { status: string, name: string, input?: any }) => {
        const existing = activeSubagents.value.find(s => s.name === subagent.name)
        if (existing) {
          existing.status = subagent.status as any
        } else {
          activeSubagents.value.push({
            name: subagent.name,
            status: subagent.status as any,
            input: subagent.input
          })
        }
        scrollToBottom()
      },
      // onScreenshot
      (screenshot: { b64: string, step: number, has_omniparser: boolean, action?: string, click?: ClickPos | null }) => {
        currentScreenshot.value = screenshot
        showScreenViewer.value = true
        // Reset thinking indicator
        isThinking.value = false
        if (_thinkingTimer) clearTimeout(_thinkingTimer)
        // Show click ripple if there was a click
        if (screenshot.click) {
          if (_rippleTimer) clearTimeout(_rippleTimer)
          clickRipple.value = screenshot.click
          _rippleTimer = setTimeout(() => { clickRipple.value = null }, 800)
        }
        // Start thinking timer — if no new screenshot in 2s, show thinking badge
        _thinkingTimer = setTimeout(() => {
          if (isLoading.value) isThinking.value = true
        }, 2000)
      },
      // useGeneralist
      useGeneralist.value,
      // onReasoning
      (reasoning: string) => {
        streamingReasoning.value += reasoning
      },
      // onTakeover
      (takeover: { message: string, thread_id: string, action_type: string }) => {
        takeoverState.value = takeover
      }
    )
  } catch (error) {
    console.error('Stream error', error)
    activeMessages.value.push({
      role: 'assistant',
      content: 'Connection error. Please try again.'
    })
    streamingContent.value = ''
    isLoading.value = false
  }
}

function copyMessage(content: string) {
  navigator.clipboard.writeText(content)
}

async function sendTakeoverResponse() {
  if (!takeoverState.value || !takeoverResponse.value.trim()) return
  isResuming.value = true
  try {
    await chatService.resumeThread(takeoverState.value.thread_id, takeoverResponse.value.trim())
    // Add the user's response as a message in the chat
    activeMessages.value.push({ role: 'user', content: takeoverResponse.value.trim() })
    takeoverState.value = null
    takeoverResponse.value = ''
  } catch (err) {
    console.error('Resume error', err)
    activeMessages.value.push({ role: 'assistant', content: 'Error al enviar respuesta. Inténtalo de nuevo.' })
  } finally {
    isResuming.value = false
  }
}
</script>

<template>
  <div class="flex h-full w-full relative overflow-hidden bg-transparent">

    <!-- Main Chat Area -->
    <div class="flex flex-col flex-1 min-w-0 relative overflow-hidden">
    
    <!-- Loading Messages Spinner -->
    <div v-if="isLoadingMessages" class="flex-1 flex items-center justify-center">
      <div class="flex flex-col items-center gap-4">
        <div class="relative w-10 h-10">
          <svg class="animate-spin w-full h-full text-white/10" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" />
          </svg>
          <svg class="absolute top-0 left-0 w-full h-full text-white animate-spin" style="animation-duration: 1.5s" viewBox="0 0 24 24" fill="none">
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
        </div>
      </div>
    </div>
    
    <!-- Welcome State -->
    <WelcomeState 
      v-else-if="activeMessages.length === 0 && !isLoading"
      @select="handleSendMessage" 
    />
    
    <!-- Messages -->
    <div v-else ref="chatContainer" class="flex-1 overflow-y-auto pt-6 pb-48 scroll-smooth">
      <div class="max-w-3xl mx-auto px-4 md:px-6 space-y-6">
        <div 
          v-for="(msg, idx) in activeMessages" 
          :key="idx"
        >
          <!-- User Message — right aligned bubble, no avatar -->
          <div v-if="msg.role === 'user'" class="flex justify-end mb-6">
            <div class="bg-[#2f2f2f] text-[#ececec] px-5 py-3 rounded-xl rounded-br-sm max-w-[80%] text-[15px] leading-[1.7] border border-white/[0.03]">
              <div class="whitespace-pre-wrap">{{ msg.content }}</div>
            </div>
          </div>
          
          <!-- Assistant Message — full width with model header -->
          <div v-else class="mb-6">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-7 h-7 rounded-full bg-white text-black flex items-center justify-center font-bold text-[9px]">
                OI
              </div>
              <span class="text-[14px] font-medium text-white">Aura AI</span>
            </div>
            <div class="pl-10">
              <ReasoningBlock v-if="msg.reasoning_content" :content="msg.reasoning_content" />
              <MarkdownRenderer :content="msg.content" />
              <!-- Action Icons -->
              <div class="flex items-center gap-0.5 mt-3 -ml-1.5">
                <button @click="copyMessage(msg.content)" class="p-1.5 text-[#7a7a7a] hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="Copy">
                  <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                </button>
                <button class="p-1.5 text-[#7a7a7a] hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="Like">
                  <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"/></svg>
                </button>
                <button class="p-1.5 text-[#7a7a7a] hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="Dislike">
                  <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z"/></svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Streaming in-progress message -->
        <div v-if="isLoading" class="mb-6">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-7 h-7 rounded-full bg-white text-black flex items-center justify-center font-bold text-[9px]">
              OI
            </div>
            <span class="text-[14px] font-medium text-white">Aura AI</span>
          </div>
          <div class="pl-10">
            <!-- Subagent Cards -->
            <div v-if="activeSubagents.length > 0" class="mb-3 flex flex-col gap-2">
              <div v-for="subagent in activeSubagents" :key="subagent.name" 
                   class="flex items-center gap-2 bg-white/[0.03] px-3 py-2 rounded-lg border border-white/5 text-xs text-white/80 max-w-fit">
                <svg v-if="subagent.status === 'running'" class="animate-spin w-3 h-3 text-white/50" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <svg v-else-if="subagent.status === 'complete'" class="w-3 h-3 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <svg v-else class="w-3 h-3 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                
                <span class="font-medium font-mono text-white/90">{{ subagent.name }}</span>
                <span v-if="subagent.status === 'running'" class="text-white/50">ejecutando operación...</span>
                <span v-else-if="subagent.status === 'complete'" class="text-white/50 text-emerald-500/80">operación completada</span>
                <span v-else class="text-white/50 text-red-400/80">falló</span>
              </div>
            </div>

            <ReasoningBlock v-if="streamingReasoning" :content="streamingReasoning" />
            <div v-if="streamingContent">
              <MarkdownRenderer :content="streamingContent" />
              <div class="inline-block w-[2px] h-[18px] bg-white/60 ml-0.5 animate-pulse align-text-bottom"></div>
            </div>
            <div v-else class="flex items-center gap-2 py-2">
              <div class="flex items-center gap-1">
                <div class="w-2 h-2 bg-[#7a7a7a] rounded-full animate-bounce [animation-duration:0.8s]"></div>
                <div class="w-2 h-2 bg-[#7a7a7a] rounded-full animate-bounce [animation-duration:0.8s] [animation-delay:0.15s]"></div>
                <div class="w-2 h-2 bg-[#7a7a7a] rounded-full animate-bounce [animation-duration:0.8s] [animation-delay:0.3s]"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Generalist Toggle + Chat Input -->
    <div class="absolute bottom-0 left-0 right-0">
      <!-- Generalist Mode Toggle -->
      <div class="flex justify-center mb-2 px-4">
        <button
          @click="useGeneralist = !useGeneralist"
          :class="[
            'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-all duration-200',
            useGeneralist
              ? 'bg-white/10 border-white/20 text-white'
              : 'bg-transparent border-white/10 text-white/40 hover:text-white/60 hover:border-white/20'
          ]"
          :title="useGeneralist ? 'Modo Generalista activo — llama3.1:8b orquesta al experto industrial' : 'Activar Modo Generalista'"
        >
          <span>{{ useGeneralist ? '🌐' : '⚙️' }}</span>
          <span>{{ useGeneralist ? 'Generalista' : 'Experto' }}</span>
        </button>
      </div>
      <ChatInput 
        :disabled="isLoading || !!takeoverState"
        @send="handleSendMessage"
      />
    </div>
    </div><!-- end main chat area -->

    <!-- Live Screen Viewer Panel (RIGHT side) -->
    <transition name="slide-right">
      <div
        v-if="showScreenViewer && currentScreenshot"
        class="hidden lg:flex flex-col flex-shrink-0 w-[480px] border-l border-white/[0.06] bg-[#141414]"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full" :class="isLoading ? 'bg-emerald-400 animate-pulse' : 'bg-white/30'"></div>
            <span class="text-[12px] font-medium text-white/70 font-mono">sistema1-vl</span>
            <span class="text-[11px] text-white/30">step {{ currentScreenshot.step }}</span>
            <span v-if="currentScreenshot.has_omniparser" class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">SoM</span>
          </div>
          <button @click="showScreenViewer = false" class="text-white/30 hover:text-white/60 transition-colors p-1 rounded hover:bg-white/5">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <!-- Screenshot with crossfade between frames -->
        <div class="flex-1 overflow-hidden relative bg-black">
          <transition name="screenshot-fade" mode="out-in">
            <img
              :key="currentScreenshot.step"
              :src="`data:image/png;base64,${currentScreenshot.b64}`"
              class="w-full h-full object-contain"
              alt="Agent screen"
            />
          </transition>

          <!-- Click ripple animation -->
          <div
            v-if="clickRipple"
            class="click-ripple"
            :style="{ left: clickRipple.x + '%', top: clickRipple.y + '%' }"
          />

          <!-- Thinking badge (AI processing state) -->
          <transition name="action-fade">
            <div
              v-if="isThinking"
              class="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 backdrop-blur-md border border-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.15)]"
            >
              <div class="relative flex items-center justify-center">
                <div class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
                <div class="absolute w-4 h-4 rounded-full bg-emerald-400/20 animate-ping"></div>
              </div>
              <span class="text-[11px] font-medium text-emerald-300 tracking-wide">Pensando...</span>
              <div class="flex gap-0.5">
                <div class="w-1 h-1 rounded-full bg-emerald-400/60 animate-bounce" style="animation-delay: 0ms"></div>
                <div class="w-1 h-1 rounded-full bg-emerald-400/60 animate-bounce" style="animation-delay: 150ms"></div>
                <div class="w-1 h-1 rounded-full bg-emerald-400/60 animate-bounce" style="animation-delay: 300ms"></div>
              </div>
            </div>
          </transition>

          <!-- Action label overlay -->
          <transition name="action-fade">
            <div
              v-if="currentScreenshot.action"
              :key="currentScreenshot.step + '-action'"
              class="absolute bottom-3 left-3 right-3 text-[10px] font-mono text-white/50 bg-black/60 rounded px-2 py-1 truncate backdrop-blur-sm border border-white/[0.06]"
            >
              ↳ {{ currentScreenshot.action }}
            </div>
          </transition>

          <!-- Takeover overlay (Human-in-the-Loop) -->
          <transition name="action-fade">
            <div
              v-if="takeoverState"
              class="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm z-30"
            >
              <div class="bg-[#1a1a1a] border border-amber-500/30 rounded-xl px-5 py-4 max-w-[90%] w-full mx-4">
                <div class="flex items-start gap-3 mb-3">
                  <div class="w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
                  </div>
                  <p class="text-sm text-amber-200/90">{{ takeoverState.message }}</p>
                </div>
                <div class="flex gap-2">
                  <input
                    v-model="takeoverResponse"
                    type="text"
                    placeholder="Tu respuesta..."
                    class="flex-1 bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-amber-500/50"
                    @keyup.enter="sendTakeoverResponse"
                  />
                  <button
                    @click="sendTakeoverResponse"
                    :disabled="isResuming || !takeoverResponse.trim()"
                    class="px-4 py-2 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-sm font-medium rounded-lg border border-amber-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {{ isResuming ? '...' : 'Enviar' }}
                  </button>
                </div>
              </div>
            </div>
          </transition>
        </div>
        <!-- Loading scan-line bar -->
        <div v-if="isLoading" class="h-[2px] bg-white/5 overflow-hidden">
          <div class="h-full bg-emerald-400/50 animate-scan"></div>
        </div>
      </div>
    </transition>

  </div><!-- end outer flex -->
</template>

<style scoped>
/* ── Panel slide-in from right ────────────────────────────────────────────── */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.25s ease;
}
.slide-right-enter-from,
.slide-right-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

/* ── Screenshot crossfade (video-like frame transition) ───────────────────── */
.screenshot-fade-enter-active {
  transition: opacity 0.15s ease;
}
.screenshot-fade-leave-active {
  transition: opacity 0.1s ease;
  position: absolute;
  inset: 0;
}
.screenshot-fade-enter-from,
.screenshot-fade-leave-to {
  opacity: 0;
}

/* ── Action label fade ────────────────────────────────────────────────────── */
.action-fade-enter-active,
.action-fade-leave-active {
  transition: opacity 0.3s ease;
}
.action-fade-enter-from,
.action-fade-leave-to {
  opacity: 0;
}

/* ── Scan-line animation (loading indicator) ──────────────────────────────── */
@keyframes scan {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
.animate-scan {
  width: 25%;
  animation: scan 1.2s ease-in-out infinite;
}

/* ── Click ripple animation ────────────────────────────────────────────────── */
@keyframes ripple {
  0%   { transform: translate(-50%, -50%) scale(1);   opacity: 0.9; }
  100% { transform: translate(-50%, -50%) scale(3);   opacity: 0; }
}
@keyframes ripple-inner {
  0%   { transform: translate(-50%, -50%) scale(1);   opacity: 1; }
  40%  { transform: translate(-50%, -50%) scale(1.3); opacity: 0.8; }
  100% { transform: translate(-50%, -50%) scale(1);   opacity: 0.6; }
}
.click-ripple {
  position: absolute;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid rgba(110, 231, 183, 0.95);
  animation: ripple 0.75s ease-out forwards;
  pointer-events: none;
  z-index: 10;
}
.click-ripple::after {
  content: '';
  position: absolute;
  inset: 4px;
  border-radius: 50%;
  background: rgba(110, 231, 183, 0.5);
  animation: ripple-inner 0.75s ease-out forwards;
}
</style>
