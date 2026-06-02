import { reactive, computed } from 'vue'
import type { AuraEvent, LogLine } from '@/services/eventService'

/**
 * Global reactive store for the reactive event pipeline.
 * Uses Vue 3 reactivity (no Pinia required).
 */

export interface EventState {
  events: AuraEvent[]
  selectedId: number | null
  isLoading: boolean
  sseConnected: boolean
  unreadCount: number
}

export interface EventDerivedState {
  selectedEvent: AuraEvent | null
  pendingApprovalCount: number
}

const state = reactive<EventState>({
  events: [],
  selectedId: null,
  isLoading: false,
  sseConnected: false,
  unreadCount: 0,
})

// Ephemeral per-event state (not persisted in DB, received via SSE)
const ephemeralState = reactive<Record<number, {
  logs: LogLine[]
  triageResult: Record<string, any> | null
  historicalAnalysis: string | null
  analysisResult: string | null
}>>({})

export const useEventStore = () => {
  const selectedEvent = computed<AuraEvent | null>(() => {
    if (!state.selectedId) return null
    return state.events.find(e => e.id === state.selectedId) || null
  })

  const pendingApprovalCount = computed(() =>
    state.events.filter(e => e.status === 'awaiting_approval').length
  )

  function getEventLogs(eventId: number): LogLine[] {
    const es = ephemeralState[eventId]
    return es ? es.logs : []
  }

  function getTriageResult(eventId: number): Record<string, any> | null {
    const es = ephemeralState[eventId]
    return es ? es.triageResult : null
  }

  function getHistoricalAnalysis(eventId: number): string | null {
    const es = ephemeralState[eventId]
    return es ? es.historicalAnalysis : null
  }

  function getAnalysisResult(eventId: number): string | null {
    const es = ephemeralState[eventId]
    return es ? es.analysisResult : null
  }

  function ensureEphemeral(eventId: number) {
    if (!ephemeralState[eventId]) {
      ephemeralState[eventId] = {
        logs: [],
        triageResult: null,
        historicalAnalysis: null,
        analysisResult: null,

      }
    }
  }

  function appendLog(eventId: number, log: LogLine) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].logs.push(log)
  }

  function setTriageResult(eventId: number, result: Record<string, any>) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].triageResult = result
  }

  function setHistoricalAnalysis(eventId: number, text: string) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].historicalAnalysis = text
  }

  function setAnalysisResult(eventId: number, text: string) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].analysisResult = text
  }

  // ── Store methods used by EventsView.vue ──

  function setEvents(events: AuraEvent[]) {
    state.events = events
  }

  function selectEvent(eventId: number) {
    state.selectedId = eventId
  }

  function updateEvent(partial: Partial<AuraEvent> & { id: number }) {
    const idx = state.events.findIndex(e => e.id === partial.id)
    if (idx >= 0) {
      Object.assign(state.events[idx], partial)
    }
  }

  return {
    state,
    selectedEvent,
    pendingApprovalCount,
    getEventLogs,
    getTriageResult,
    getHistoricalAnalysis,
    getAnalysisResult,
    ensureEphemeral,
    appendLog,
    setTriageResult,
    setHistoricalAnalysis,
    setAnalysisResult,

    setEvents,
    selectEvent,
    updateEvent,

  }
}
