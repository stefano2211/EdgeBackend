<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import eventService, {
  type AuraEvent,
  type EventSeverityText,
  type EventStatus,
  type SSEPayload,
  type DemoPreset,
  DEMO_PRESETS,
} from '@/services/eventService'
import reactiveConfigService from '@/services/reactiveConfigService'
import { webhookService, type WebhookSource } from '@/services/webhookService'
import { useEventStore } from '@/stores/events'
import DynamicMetricCard from '@/components/events/DynamicMetricCard.vue'
import ConfidenceBadge from '@/components/events/ConfidenceBadge.vue'
import SeverityBar from '@/components/events/SeverityBar.vue'
import AdminModal from '@/components/events/AdminModal.vue'

// ── Store ─────────────────────────────────────────────────────────────────────
const store = useEventStore()
const { state, selectedEvent, pendingApprovalCount } = store
const router = useRouter()
const route = useRoute()

// ── Local UI state ────────────────────────────────────────────────────────────
const isLoading = ref(false)
const sseConnected = ref(false)
let sseSource: EventSource | null = null
const showConfigBanner = ref(false)

// Filters (agnostic)
interface FilterDef {
  key: keyof AuraEvent
  label: string
  order?: string[]
  labelMap?: Record<string, string>
}

const filterDefinitions: FilterDef[] = [
  {
    key: 'severity_text',
    label: 'Severidad',
    order: ['critical', 'error', 'warning', 'info', 'debug'],
    labelMap: { critical: 'Crítica', error: 'Error', warning: 'Advertencia', info: 'Info', debug: 'Debug' },
  },
  {
    key: 'status',
    label: 'Estado',
    order: ['pending', 'analyzing', 'awaiting_approval', 'executing', 'completed', 'failed', 'suppressed'],
    labelMap: { pending: 'Pendiente', analyzing: 'Analizando…', awaiting_approval: 'Esperando aprobación', executing: 'Ejecutando…', completed: 'Completado', failed: 'Fallido', suppressed: 'Suprimido' },
  },
  {
    key: 'source',
    label: 'Fuente',
  },
]

const activeFilters = ref<Record<string, string>>({
  severity_text: '',
  status: '',
  source: '',
})

const openFilterDropdown = ref<string | null>(null)

function toggleFilterDropdown(key: string) {
  if (openFilterDropdown.value === key) {
    openFilterDropdown.value = null
  } else {
    openFilterDropdown.value = key
  }
}

function selectFilterOption(key: string, value: string) {
  activeFilters.value[key] = value
  openFilterDropdown.value = null
}

const hasActiveFilters = computed(() => {
  return Object.values(activeFilters.value).some(v => v !== '')
})

function resetFilters() {
  for (const key in activeFilters.value) {
    activeFilters.value[key] = ''
  }
}

const closeAllFilterDropdowns = (e: MouseEvent) => {
  if (!(e.target as Element).closest('.filter-dropdown-container')) {
    openFilterDropdown.value = null
  }
}

// Modals
const showCreateModal = ref(false)

// Create form
const newEvent = ref({ severity_text: 'warning' as EventSeverityText, title: '', description: '' })
const isCreating = ref(false)

// Webhook
const webhooksList = ref<WebhookSource[]>([])
const selectedWebhookSlug = ref<string | null>(null)
const webhookSentId = ref<string | null>(null)
const isLoadingWebhooks = ref(false)

// Custom event extra JSON data
const customDataJson = ref('')

// Demo presets
const triggeringPresetId = ref<string | null>(null)
const presets = DEMO_PRESETS

// Tabs
const activeTab = ref<'overview' | 'evidence' | 'pipeline'>('overview')

// Feedback
const feedbackSubmitted = ref(false)
const feedbackSubmitting = ref(false)

// ── Computed ──────────────────────────────────────────────────────────────────
const filteredEvents = computed(() => {
  return state.events.filter(e => {
    for (const def of filterDefinitions) {
      const val = activeFilters.value[def.key]
      if (val && (e as any)[def.key] !== val) return false
    }
    return true
  })
})

const eventLogs = computed(() => {
  if (!selectedEvent.value) return []
  return store.getEventLogs(selectedEvent.value.id)
})

// ── Dynamic filter options (agnostic) ─────────────────────────────────────────
const filterOptions = computed(() => {
  const result: Record<string, { label: string; options: { value: string; label: string }[] }> = {}
  for (const def of filterDefinitions) {
    const rawValues = new Set(state.events.map(e => String((e as any)[def.key] ?? '')).filter(v => v))
    let sorted: string[]
    if (def.order) {
      sorted = def.order.filter(o => rawValues.has(o))
    } else {
      sorted = Array.from(rawValues).sort((a, b) => a.localeCompare(b))
    }
    result[def.key] = {
      label: def.label,
      options: sorted.map(v => ({
        value: v,
        label: def.labelMap?.[v] ?? v,
      })),
    }
  }
  return result
})

// Auto-clear stale filter selections when the dataset changes
watch(filterOptions, (opts) => {
  for (const def of filterDefinitions) {
    const current = activeFilters.value[def.key]
    if (current && !opts[def.key].options.some(o => o.value === current)) {
      activeFilters.value[def.key] = ''
    }
  }
})

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadEvents() {
  isLoading.value = true
  try {
    const res = await eventService.listEvents({ limit: 100 })
    store.setEvents(res.items)
  } catch (err) {
    console.error('Failed to load events', err)
  } finally {
    isLoading.value = false
  }
}

async function refreshSelected() {
  if (!selectedEvent.value) return
  try {
    const ev = await eventService.getEvent(selectedEvent.value.id)
    store.updateEvent(ev)
  } catch {}
}

// ── SSE ───────────────────────────────────────────────────────────────────────
function connectSSE() {
  if (sseSource) sseSource.close()
  sseSource = eventService.openSSEStream(
    (payload: SSEPayload) => {
      handleSSE(payload)
    },
    () => {
      sseConnected.value = false
      setTimeout(connectSSE, 5000)
    }
  )
  if (sseSource) {
    sseSource.onopen = () => { sseConnected.value = true }
  }
}

function handleSSE(payload: SSEPayload) {
  const eventType = payload.type
  const data = payload.data || {}
  const eventId = Number(data.id)

  if (!eventId || isNaN(eventId)) return

  // Ensure ephemeral state exists
  store.ensureEphemeral(eventId)

  switch (eventType) {
    case 'connected':
      sseConnected.value = true
      return

    case 'new_event':
      state.unreadCount++
      loadEvents()
      return

    case 'analysis_result':
      store.updateEvent({
        id: eventId,
        agent_analysis: data.result,
      })
      break

    case 'diagnosis_result':
      store.updateEvent({
        id: eventId,
        agent_diagnosis: data.diagnosis,
      })
      break

    case 'planner_result':
      store.updateEvent({
        id: eventId,
        agent_plan: data.plan,
      })
      break

    case 'log_line':
      store.appendLog(eventId, {
        timestamp: data.timestamp,
        level: data.level,
        message: data.message,
      })
      break

    case 'status_update':
    case 'event_update':
      store.updateEvent({
        id: eventId,
        status: data.status,
        severity_text: data.severity_text,
        severity_number: data.severity_number,
        title: data.title,
        updated_at: data.updated_at,
      })
      if (selectedEvent.value?.id === eventId) {
        refreshSelected()
      }
      loadEvents()
      break
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────
async function createWebhookEvent() {
  if (!newEvent.value.title.trim()) return
  if (!selectedWebhookSlug.value) {
    alert('Selecciona un webhook')
    return
  }
  isCreating.value = true
  try {
    // Build payload from form + custom JSON data
    let extraData: Record<string, any> = {}
    try {
      if (customDataJson.value.trim()) {
        extraData = JSON.parse(customDataJson.value)
      }
    } catch {
      alert('JSON inválido en el campo de datos personalizados')
      return
    }
    await sendToWebhook({
      title: newEvent.value.title,
      description: newEvent.value.description,
      severity: newEvent.value.severity_text,
      ...extraData
    })
    showCreateModal.value = false
    newEvent.value = { severity_text: 'warning', title: '', description: '' }
    customDataJson.value = ''
    await loadEvents()
  } catch (err) {
    console.error('Failed to create event', err)
  } finally {
    isCreating.value = false
  }
}

async function triggerPresetWebhook(preset: DemoPreset) {
  if (!selectedWebhookSlug.value) return
  triggeringPresetId.value = preset.id
  try {
    await sendToWebhook({
      title: preset.title,
      description: preset.description,
      severity: preset.severity_text,
      ...preset.data,
      _demo: true,
      _preset_id: preset.id,
      timestamp: new Date().toISOString(),
    }, preset.id)
    showCreateModal.value = false
    await loadEvents()
  } catch (err) {
    console.error('Failed to trigger preset', err)
  } finally {
    triggeringPresetId.value = null
  }
}

async function loadWebhooksForModal() {
  if (webhooksList.value.length > 0) return
  isLoadingWebhooks.value = true
  try {
    webhooksList.value = await webhookService.list()
    if (webhooksList.value.length > 0 && !selectedWebhookSlug.value) {
      selectedWebhookSlug.value = webhooksList.value[0].slug
    }
  } catch {}
  isLoadingWebhooks.value = false
}

async function sendToWebhook(payload: any, presetId?: string) {
  if (!selectedWebhookSlug.value) return
  const baseUrl = import.meta.env.PROD
    ? (import.meta.env.VITE_API_URL || window.location.origin)
    : window.location.origin
  const url = `${baseUrl}/webhooks/${selectedWebhookSlug.value}/receive`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  if (presetId) {
    webhookSentId.value = presetId
    setTimeout(() => webhookSentId.value = null, 2000)
  }
}



async function submitFeedback(feedbackType: 'false_positive' | 'wrong_severity' | 'other') {
  if (!selectedEvent.value) return
  feedbackSubmitting.value = true
  try {
    await eventService.submitFeedback(selectedEvent.value.id, {
      feedback_type: feedbackType,
      comment: undefined,
    })
    feedbackSubmitted.value = true
  } catch (err) {
    console.error('Failed to submit feedback', err)
  } finally {
    feedbackSubmitting.value = false
  }
}

function selectEvent(event: AuraEvent) {
  const prevId = selectedEvent.value?.id
  store.selectEvent(event.id)
  // Reset UI state for new event
  if (prevId && prevId !== event.id) {
    feedbackSubmitted.value = false
    feedbackSubmitting.value = false
    activeTab.value = 'overview'
  }
}

async function checkReactiveConfig() {
  try {
    const [tools, kbs] = await Promise.all([
      reactiveConfigService.listTools(),
      reactiveConfigService.listKnowledgeBases(),
    ])
    const hasAnyEnabled = tools.some(t => t.is_enabled) || kbs.some(k => k.is_enabled_reactive)
    showConfigBanner.value = !hasAnyEnabled
  } catch (e) {
    showConfigBanner.value = false
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  loadEvents()
  connectSSE()
  checkReactiveConfig()
  window.addEventListener('click', closeAllFilterDropdowns)
})

watch(showCreateModal, (val) => {
  if (val) {
    loadWebhooksForModal()
  }
})

onUnmounted(() => {
  sseSource?.close()
  window.removeEventListener('click', closeAllFilterDropdowns)
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function severityColor(s: EventSeverityText) {
  switch (s) {
    case 'critical': return 'bg-red-500/15 text-red-400 border-red-500/30'
    case 'error': return 'bg-orange-500/15 text-orange-400 border-orange-500/30'
    case 'warning': return 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30'
    case 'info': return 'bg-blue-500/15 text-blue-400 border-blue-500/30'
    case 'debug': return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    default: return 'bg-white/5 text-[#a0a0a0] border-white/10'
  }
}

function severityDot(s: EventSeverityText) {
  switch (s) {
    case 'critical': return 'bg-red-500'
    case 'error': return 'bg-orange-500'
    case 'warning': return 'bg-yellow-500'
    case 'info': return 'bg-blue-500'
    case 'debug': return 'bg-emerald-500'
    default: return 'bg-[#555]'
  }
}

function severityLabel(s: EventSeverityText) {
  return {
    critical: 'Crítica',
    error: 'Error',
    warning: 'Advertencia',
    info: 'Info',
    debug: 'Debug',
  }[s] ?? s
}

function statusColor(s: EventStatus) {
  return {
    pending: 'text-gray-400',
    analyzing: 'text-blue-400',
    awaiting_approval: 'text-amber-400',
    executing: 'text-purple-400',
    completed: 'text-emerald-400',
    failed: 'text-red-400',
  }[s] ?? 'text-gray-400'
}

function statusLabel(s: EventStatus) {
  return {
    pending: 'Pendiente',
    analyzing: 'Analizando…',
    awaiting_approval: 'Esperando aprobación',
    executing: 'Ejecutando…',
    completed: 'Completado',
    failed: 'Fallido',
  }[s] ?? s
}

function logColor(level: string) {
  return {
    info: 'text-blue-300',
    debug: 'text-gray-400',
    warn: 'text-amber-300',
    error: 'text-red-300',
  }[level] ?? 'text-gray-300'
}

function formatDate(d: string) {
  return new Date(d).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function formatTime(d: string) {
  return new Date(d).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<template>
  <div class="flex h-full bg-[#0f0f0f] text-white overflow-hidden">

    <!-- ── LEFT: Event list ─────────────────────────────────────────────── -->
    <div class="w-[340px] shrink-0 flex flex-col border-r border-white/[0.06] h-full bg-[#0d0d0d]">

      <!-- Header -->
      <div class="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <span class="font-semibold text-[15px] text-white tracking-tight">Centro de operaciones</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5" :title="sseConnected ? 'En vivo' : 'Reconectando…'">
            <div class="w-1.5 h-1.5 rounded-full" :class="sseConnected ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'"></div>
            <span class="text-[10px] text-[#666] uppercase tracking-wider">{{ sseConnected ? 'EN VIVO' : 'SIN CONEXIÓN' }}</span>
          </div>
          <button @click="showCreateModal = true" class="p-1.5 hover:bg-white/8 rounded-lg transition-colors text-[#b4b4b4] hover:text-white" title="Nuevo evento manual">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
          </button>
          <button @click="router.push('/admin/users')" class="p-1.5 hover:bg-white/8 rounded-lg transition-colors text-[#b4b4b4] hover:text-white" title="Panel de Administración">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </button>
          <button @click="loadEvents" class="p-1.5 hover:bg-white/8 rounded-lg transition-colors text-[#b4b4b4] hover:text-white" title="Refrescar">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="isLoading && 'animate-spin'"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="px-4 py-2 border-b border-white/[0.06] flex gap-2 flex-wrap items-center">
        <div 
          v-for="def in filterDefinitions" 
          :key="def.key" 
          class="relative filter-dropdown-container"
        >
          <button
            @click.stop="toggleFilterDropdown(def.key)"
            class="flex items-center gap-2 text-[12px] bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-[#ececec] hover:bg-white/10 hover:border-white/20 transition-all font-medium focus:outline-none focus:border-white/20"
            :class="{ '!border-white/20 bg-white/10': openFilterDropdown === def.key }"
          >
            <span>{{ activeFilters[def.key] ? (def.labelMap?.[activeFilters[def.key]] ?? activeFilters[def.key]) : def.label }}</span>
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              width="12" 
              height="12" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              stroke-width="2.5" 
              stroke-linecap="round" 
              stroke-linejoin="round" 
              class="text-[#7a7a7a] transition-transform duration-200"
              :class="{ 'rotate-180 text-white': openFilterDropdown === def.key }"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>

          <Transition name="fade-popover">
            <div
              v-if="openFilterDropdown === def.key"
              class="absolute left-0 mt-1.5 w-48 bg-[#161616] border border-white/[0.08] rounded-xl shadow-2xl py-1.5 z-[99] backdrop-blur-md overflow-hidden"
            >
              <button
                @click="selectFilterOption(def.key, '')"
                class="w-full text-left px-3.5 py-2 text-[12px] transition-colors flex items-center justify-between"
                :class="!activeFilters[def.key] ? 'text-violet-400 bg-violet-500/10 font-semibold' : 'text-[#7a7a7a] hover:bg-white/5 hover:text-white'"
              >
                <span>Todo ({{ def.label }})</span>
                <svg v-if="!activeFilters[def.key]" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="text-violet-400"><polyline points="20 6 9 17 4 12"></polyline></svg>
              </button>
              
              <div class="border-t border-white/[0.04] my-1"></div>

              <button
                v-for="opt in filterOptions[def.key]?.options"
                :key="opt.value"
                @click="selectFilterOption(def.key, opt.value)"
                class="w-full text-left px-3.5 py-2 text-[12px] transition-colors flex items-center justify-between"
                :class="activeFilters[def.key] === opt.value ? 'text-violet-400 bg-violet-500/10 font-semibold' : 'text-[#b4b4b4] hover:bg-white/5 hover:text-white'"
              >
                <span>{{ opt.label }}</span>
                <svg v-if="activeFilters[def.key] === opt.value" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="text-violet-400"><polyline points="20 6 9 17 4 12"></polyline></svg>
              </button>
            </div>
          </Transition>
        </div>

        <button
          v-if="hasActiveFilters"
          @click="resetFilters"
          class="text-[11px] font-semibold text-red-400 hover:text-red-300 transition-colors ml-2 px-2 py-1 rounded-lg hover:bg-red-500/10 flex items-center gap-1"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          Limpiar
        </button>
      </div>

      <!-- List -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="isLoading && filteredEvents.length === 0" class="flex items-center justify-center h-24 text-[#7a7a7a] text-sm">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="animate-spin mr-2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          Cargando…
        </div>
        <div v-else-if="filteredEvents.length === 0" class="flex flex-col items-center justify-center h-32 text-[#7a7a7a] text-sm gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          Sin eventos
        </div>
        <div
          v-for="event in filteredEvents"
          :key="event.id"
          @click="selectEvent(event)"
          class="px-3 py-3 border-b border-white/[0.04] cursor-pointer transition-colors group"
          :class="selectedEvent?.id === event.id ? 'bg-white/[0.07]' : 'hover:bg-white/[0.04]'"
        >
          <div class="flex items-start gap-2.5">
            <div class="mt-1.5 w-2 h-2 rounded-full shrink-0" :class="severityDot(event.severity_text)"></div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-0.5">
                <span class="text-[13px] font-medium text-[#ececec] truncate flex-1">{{ event.title }}</span>
                <span class="text-[11px] shrink-0" :class="statusColor(event.status)">
                  <span v-if="event.status === 'analyzing'" class="inline-block w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse mr-1"></span>
                  <span v-if="event.status === 'executing'" class="inline-block w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse mr-1"></span>
                  {{ statusLabel(event.status) }}
                </span>
              </div>
              <div class="flex items-center gap-2 text-[12px] text-[#7a7a7a]">
                <span :class="['px-1.5 py-0.5 rounded text-[10px] font-semibold border', severityColor(event.severity_text)]">{{ event.severity_text.toUpperCase() }}</span>
                <span class="truncate">{{ event.source }}</span>
                <span class="ml-auto shrink-0 text-[11px]">{{ formatDate(event.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── RIGHT: Event detail (Gradio-style) ─────────────────────────────── -->
    <div class="flex-1 flex flex-col h-full overflow-hidden">

      <!-- Config banner -->
      <div v-if="showConfigBanner" class="px-4 py-3 bg-purple-500/10 border-b border-purple-500/20 flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-purple-400"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>
          <span class="text-[12px] text-purple-300">No tienes herramientas ni bases de conocimiento activadas para eventos reactivos.</span>
        </div>
        <button
          @click="router.push('/config/tools')"
          class="shrink-0 px-3 py-1 rounded-lg text-[11px] font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 transition-colors"
        >
          Configurar ahora
        </button>
      </div>

      <!-- Empty state -->
      <div v-if="!selectedEvent" class="flex-1 flex flex-col items-center justify-center text-[#7a7a7a] gap-3">
        <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
        <p class="text-sm">Selecciona un evento para ver el detalle</p>
      </div>

      <template v-else>
        <!-- Detail header -->
        <div class="px-6 py-4 border-b border-white/[0.06] flex items-start justify-between gap-4">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <span :class="['px-2 py-0.5 rounded text-[11px] font-bold border', severityColor(selectedEvent.severity_text)]">
                {{ selectedEvent.severity_text.toUpperCase() }}
              </span>
              <span class="text-[12px] text-[#7a7a7a]">{{ selectedEvent.source }}</span>
            </div>
            <h2 class="text-[16px] font-semibold text-white leading-snug">{{ selectedEvent.title }}</h2>
            <p class="text-[13px] text-[#b4b4b4] mt-1">{{ selectedEvent.description }}</p>
          </div>
          <div class="flex gap-2 shrink-0">
            <button @click="refreshSelected" class="p-2 hover:bg-white/8 rounded-lg transition-colors text-[#b4b4b4] hover:text-white" title="Refrescar">
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>
            </button>
          </div>
        </div>

        <!-- Detail body with tabs -->
        <div class="flex-1 flex flex-col overflow-hidden bg-[#0a0a0a]">

          <!-- Enhanced header meta -->
          <div class="px-6 py-3 border-b border-white/[0.06] flex items-center gap-4 flex-wrap">
            <SeverityBar v-if="selectedEvent.severity_number" :number="selectedEvent.severity_number" class="w-[200px]" />
            <div class="flex items-center gap-2 text-[11px] text-[#7a7a7a]">
              <span class="px-1.5 py-0.5 rounded bg-white/5 text-[#a0a0a0]">{{ selectedEvent.event_type }}</span>
              <span v-if="selectedEvent.domain" class="px-1.5 py-0.5 rounded bg-white/5 text-[#a0a0a0]">{{ selectedEvent.domain }}</span>
              <span v-if="selectedEvent.correlation_group_id" class="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">Group #{{ selectedEvent.correlation_group_id }}</span>
            </div>
          </div>

          <!-- Tabs -->
          <div class="px-6 pt-4 flex gap-1 border-b border-white/[0.06]">
            <button
              v-for="tab in [
                { key: 'overview', label: 'Resumen', icon: 'M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5' },
                { key: 'evidence', label: 'Evidencia', icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8' },
                { key: 'pipeline', label: 'Registro del pipeline', icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' },
              ]"
              :key="tab.key"
              @click="activeTab = tab.key as any"
              class="px-4 py-2 text-[12px] font-medium rounded-t-lg transition-colors flex items-center gap-1.5 border-b-2"
              :class="activeTab === tab.key ? 'text-white border-white/30 bg-white/5' : 'text-[#7a7a7a] border-transparent hover:text-[#b4b4b4]'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path :d="tab.icon"/></svg>
              {{ tab.label }}
            </button>
          </div>

          <!-- Tab content -->
          <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">

            <!-- ── TAB: Overview ── -->
            <template v-if="activeTab === 'overview'">

              <!-- Analysis -->
              <div v-if="selectedEvent?.agent_analysis" class="bg-[#111] rounded-xl border border-blue-500/20 overflow-hidden">
                <div class="px-4 py-2.5 bg-gradient-to-r from-blue-500/10 to-transparent border-b border-blue-500/15 flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-blue-400"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                  <span class="text-[11px] font-bold text-blue-400 uppercase tracking-wider">ANÁLISIS</span>
                  <ConfidenceBadge :text="selectedEvent?.agent_analysis" class="ml-auto" />
                </div>
                <div class="px-5 py-4 text-[13px] text-[#d8d8d8] leading-relaxed whitespace-pre-wrap">{{ selectedEvent?.agent_analysis }}</div>
              </div>

              <!-- Diagnosis -->
              <div v-if="selectedEvent?.agent_diagnosis" class="bg-[#111] rounded-xl border border-purple-500/20 overflow-hidden">
                <div class="px-4 py-2.5 bg-gradient-to-r from-purple-500/10 to-transparent border-b border-purple-500/15 flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-purple-400"><path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5"/><path d="M8.5 8.5v.01"/><path d="M16 15.5v.01"/></svg>
                  <span class="text-[11px] font-bold text-purple-400 uppercase tracking-wider">DIAGNÓSTICO</span>
                </div>
                <div class="px-5 py-4 text-[13px] text-[#d8d8d8] leading-relaxed whitespace-pre-wrap">{{ selectedEvent?.agent_diagnosis }}</div>
              </div>

              <!-- Remediation Plan -->
              <div v-if="selectedEvent?.agent_plan" class="bg-[#111] rounded-xl border border-emerald-500/20 overflow-hidden">
                <div class="px-4 py-2.5 bg-gradient-to-r from-emerald-500/10 to-transparent border-b border-emerald-500/15 flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                  <span class="text-[11px] font-bold text-emerald-400 uppercase tracking-wider">PLAN DE REMEDIACIÓN</span>
                </div>
                <div class="px-5 py-4 text-[13px] text-[#d8d8d8] leading-relaxed whitespace-pre-wrap">{{ selectedEvent?.agent_plan }}</div>
              </div>

              <!-- Meta -->
              <div class="flex items-center gap-4 flex-wrap px-4 py-2.5 bg-[#111] border border-white/[0.06] rounded-xl text-[11px] text-[#7a7a7a]">
                <div class="flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-white/20"></span>Creado: <span class="text-[#ececec]">{{ formatDate(selectedEvent.created_at) }}</span></div>
                <div v-if="selectedEvent.resolved_at" class="flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500/50"></span>Resuelto: <span class="text-[#ececec]">{{ formatDate(selectedEvent.resolved_at) }}</span></div>
              </div>
            </template>

            <!-- ── TAB: Evidence ── -->
            <template v-if="activeTab === 'evidence'">

              <!-- Dynamic Metric Cards -->
              <div v-if="selectedEvent.body && Object.keys(selectedEvent.body).length > 0">
                <div class="text-[11px] font-bold text-[#7a7a7a] uppercase tracking-wider mb-2">MÉTRICAS DEL PAYLOAD</div>
                <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                  <DynamicMetricCard
                    v-for="(value, key) in selectedEvent.body"
                    :key="key"
                    :label="String(key)"
                    :value="value"
                    :class="typeof value === 'object' && value !== null && !Array.isArray(value) ? 'col-span-full' : ''"
                  />
                </div>
              </div>

              <!-- Metadata Table -->
              <div class="bg-[#111] rounded-xl border border-white/[0.08] overflow-hidden">
                <div class="px-4 py-2.5 bg-white/[0.02] border-b border-white/[0.06]">
                  <span class="text-[11px] font-bold text-[#7a7a7a] uppercase tracking-wider">METADATOS DEL EVENTO</span>
                </div>
                <div class="divide-y divide-white/[0.04]">
                  <div class="px-4 py-2 flex justify-between text-[12px]">
                    <span class="text-[#7a7a7a]">ID del evento</span>
                    <span class="text-[#ececec] font-mono">{{ selectedEvent.event_id }}</span>
                  </div>
                  <div class="px-4 py-2 flex justify-between text-[12px]">
                    <span class="text-[#7a7a7a]">Fuente</span>
                    <span class="text-[#ececec]">{{ selectedEvent.source }}</span>
                  </div>
                  <div class="px-4 py-2 flex justify-between text-[12px]">
                    <span class="text-[#7a7a7a]">Tipo</span>
                    <span class="text-[#ececec]">{{ selectedEvent.event_type }}</span>
                  </div>
                  <div class="px-4 py-2 flex justify-between text-[12px]">
                    <span class="text-[#7a7a7a]">Fecha</span>
                    <span class="text-[#ececec]">{{ formatDate(selectedEvent.timestamp) }}</span>
                  </div>
                  <div class="px-4 py-2 flex justify-between text-[12px]">
                    <span class="text-[#7a7a7a]">Clave dedup</span>
                    <span class="text-[#a0a0a0] font-mono text-[10px]">{{ selectedEvent.dedup_key || '—' }}</span>
                  </div>
                  <div v-if="selectedEvent.correlation_group_id" class="px-4 py-2 flex justify-between text-[12px]">
                    <span class="text-[#7a7a7a]">Grupo de correlación</span>
                    <span class="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px] border border-blue-500/20">#{{ selectedEvent.correlation_group_id }}</span>
                  </div>
                </div>
              </div>
            </template>

            <!-- ── TAB: Pipeline Log ── -->
            <template v-if="activeTab === 'pipeline'">

              <!-- Log Timeline -->
              <div v-if="eventLogs.length > 0" class="bg-[#0c0c0c] rounded-xl border border-white/[0.08] overflow-hidden">
                <div class="px-4 py-2.5 bg-white/[0.02] border-b border-white/[0.06]">
                  <span class="text-[11px] font-bold text-[#7a7a7a] uppercase tracking-wider">Registros del pipeline</span>
                </div>
                <div class="px-4 py-3 space-y-1 max-h-[400px] overflow-y-auto font-mono text-[11px] leading-relaxed">
                  <div v-for="(log, idx) in eventLogs" :key="idx" class="flex gap-2">
                    <span class="text-[#555] shrink-0">{{ formatTime(log.timestamp) }}</span>
                    <span :class="logColor(log.level)">{{ log.message }}</span>
                  </div>
                </div>
              </div>
            </template>

          </div>

            <!-- Feedback -->
          <div v-if="selectedEvent.status === 'completed' || selectedEvent.status === 'failed'" class="shrink-0 px-6 py-4 border-t border-white/[0.06]">
            <div v-if="!feedbackSubmitted" class="flex items-center gap-3">
              <span class="text-[12px] text-[#7a7a7a]">¿Fue correcto este análisis?</span>
              <button
                @click="submitFeedback('false_positive')"
                :disabled="feedbackSubmitting"
                class="px-3 py-1.5 rounded-lg text-[11px] font-medium border border-red-500/20 text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
              >
                Falso positivo
              </button>
              <button
                @click="submitFeedback('wrong_severity')"
                :disabled="feedbackSubmitting"
                class="px-3 py-1.5 rounded-lg text-[11px] font-medium border border-amber-500/20 text-amber-400 hover:bg-amber-500/10 transition-colors disabled:opacity-50"
              >
                Severidad incorrecta
              </button>
              <button
                @click="submitFeedback('other')"
                :disabled="feedbackSubmitting"
                class="px-3 py-1.5 rounded-lg text-[11px] font-medium border border-white/10 text-[#a0a0a0] hover:bg-white/5 transition-colors disabled:opacity-50"
              >
                Otro problema
              </button>
            </div>
            <div v-else class="text-[12px] text-emerald-400 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>
              Comentario registrado. ¡Gracias!
            </div>
          </div>

        </div>
      </template>
    </div>

    <!-- ── Create event modal (Webhook only) ──────────────────────────── -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" @click.self="showCreateModal = false">
        <div class="bg-[#141414] border border-white/[0.08] rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
          <!-- Header -->
          <div class="px-5 py-3 border-b border-white/[0.06] flex items-center justify-between shrink-0">
            <h3 class="text-[14px] font-semibold text-white">Nuevo Evento</h3>
            <div class="flex items-center gap-2">
              <template v-if="webhooksList.length > 0">
                <select
                  v-model="selectedWebhookSlug"
                  class="bg-white/[0.04] border border-white/[0.08] rounded-md px-2.5 py-1 text-[11px] text-[#ececec] focus:outline-none"
                >
                  <option v-for="wh in webhooksList" :key="wh.slug" :value="wh.slug">
                    {{ wh.name }}
                  </option>
                </select>
              </template>
              <template v-else>
                <button @click="router.push('/config/webhooks'); showCreateModal = false" class="text-[11px] text-violet-400 hover:text-violet-300 underline">
                  Configurar Webhook primero
                </button>
              </template>
            </div>
          </div>

          <!-- Body -->
          <div class="px-5 py-4 overflow-y-auto">
            <div class="space-y-3">
              <div>
                <label class="text-[10px] text-[#555] mb-1 block uppercase tracking-wider">Severidad</label>
                <select v-model="newEvent.severity_text" class="w-full bg-white/[0.03] border border-white/[0.08] rounded-lg px-3 py-1.5 text-[12px] text-[#ececec] focus:outline-none focus:border-white/20">
                  <option value="critical">Crítica</option>
                  <option value="error">Error</option>
                  <option value="warning">Advertencia</option>
                  <option value="info">Info</option>
                  <option value="debug">Debug</option>
                </select>
              </div>
              <div>
                <label class="text-[10px] text-[#555] mb-1 block uppercase tracking-wider">Título</label>
                <input v-model="newEvent.title" type="text" placeholder="Ej: Presión de caldera excede límite" class="w-full bg-white/[0.03] border border-white/[0.08] rounded-lg px-3 py-1.5 text-[12px] text-[#ececec] placeholder-[#444] focus:outline-none focus:border-white/20" />
              </div>
              <div>
                <label class="text-[10px] text-[#555] mb-1 block uppercase tracking-wider">Descripción</label>
                <textarea v-model="newEvent.description" rows="2" placeholder="Contexto del evento…" class="w-full bg-white/[0.03] border border-white/[0.08] rounded-lg px-3 py-1.5 text-[12px] text-[#ececec] placeholder-[#444] focus:outline-none focus:border-white/20 resize-none"></textarea>
              </div>
              <div>
                <label class="text-[10px] text-[#555] mb-1 block uppercase tracking-wider">Payload JSON (opcional)</label>
                <textarea
                  v-model="customDataJson"
                  rows="2"
                  placeholder='{"sensor_id": "PT-999", "value": 327.4}'
                  class="w-full bg-[#0c0c0c] border border-white/[0.08] rounded-lg px-3 py-1.5 text-[10px] text-[#888] font-mono placeholder-[#333] focus:outline-none focus:border-violet-500/40 resize-none"
                />
              </div>
            </div>

            <!-- Demo Presets -->
            <div class="mt-4 pt-3 border-t border-white/[0.06]">
              <div class="text-[10px] text-[#555] uppercase tracking-wider mb-2">Escenarios Demo</div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="p in presets"
                  :key="p.id"
                  @click="triggerPresetWebhook(p)"
                  :disabled="triggeringPresetId !== null || !selectedWebhookSlug"
                  class="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] hover:border-white/[0.12] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  :title="p.description"
                >
                  <span class="text-[11px]">{{ p.icon }}</span>
                  <span class="text-[10px] text-[#c0c0c0]">{{ p.label }}</span>
                  <span class="text-[8px] font-bold uppercase px-1 py-[1px] rounded" :class="severityColor(p.severity_text)">{{ p.severity_text[0] }}</span>
                  <svg v-if="triggeringPresetId === p.id" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin text-violet-400"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  <svg v-else-if="webhookSentId === p.id" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400"><path d="M20 6 9 17l-5-5"/></svg>
                </button>
              </div>
              <p class="text-[9px] text-[#444] mt-2">
                Datos de prueba enviados al webhook seleccionado.
              </p>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between shrink-0">
            <span class="text-[10px] text-[#444] font-mono">POST /webhooks/{slug}/receive</span>
            <div class="flex gap-2">
              <button @click="showCreateModal = false" class="px-3 py-1 text-[11px] text-[#888] hover:text-white transition-colors rounded-md hover:bg-white/5">Cancelar</button>
              <button @click="createWebhookEvent" :disabled="isCreating || !newEvent.title.trim() || !selectedWebhookSlug" class="px-3 py-1 rounded-md text-[11px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed bg-violet-600 hover:bg-violet-500 text-white">
                <svg v-if="isCreating" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin inline mr-1"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                Enviar
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>



    <!-- Admin Modal -->
    <AdminModal v-if="route.query.admin" />
  </div>
</template>

<style scoped>
.fade-popover-enter-active,
.fade-popover-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.fade-popover-enter-from,
.fade-popover-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
</style>
