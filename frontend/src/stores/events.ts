import { reactive, computed } from 'vue'
import type { AuraEvent, LogLine, LiveScreenshot } from '@/services/eventService'

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
  vlmAnalysis: string | null
  liveScreenshot: LiveScreenshot | null
  vlScreenshots: LiveScreenshot[]
  vlThoughts: string[]
  vlActions: any[]
  vlProgress: { current_step: number; max_steps: number } | null
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

  function getVlmAnalysis(eventId: number): string | null {
    const es = ephemeralState[eventId]
    return es ? es.vlmAnalysis : null
  }

  function getLiveScreenshot(eventId: number): LiveScreenshot | null {
    const es = ephemeralState[eventId]
    return es ? es.liveScreenshot : null
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
        vlmAnalysis: null,
        liveScreenshot: null,
        vlScreenshots: [],
        vlThoughts: [],
        vlActions: [],
        vlProgress: null,
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

  function setVlmAnalysis(eventId: number, text: string) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].vlmAnalysis = text
  }

  function setLiveScreenshot(eventId: number, screenshot: LiveScreenshot) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].liveScreenshot = screenshot
    ephemeralState[eventId].vlScreenshots.push(screenshot)
  }

  function addVlThought(eventId: number, thought: string) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].vlThoughts.push(thought)
  }

  function addVlAction(eventId: number, action: any) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].vlActions.push(action)
  }

  function setVlProgress(eventId: number, progress: { current_step: number; max_steps: number }) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].vlProgress = progress
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

  function getVlScreenshots(eventId: number): LiveScreenshot[] {
    const es = ephemeralState[eventId]
    return es ? es.vlScreenshots : []
  }

  function getVlThoughts(eventId: number): string[] {
    const es = ephemeralState[eventId]
    return es ? es.vlThoughts : []
  }

  function getVlActions(eventId: number): any[] {
    const es = ephemeralState[eventId]
    return es ? es.vlActions : []
  }

  function getVlProgress(eventId: number): { current_step: number; max_steps: number } | null {
    const es = ephemeralState[eventId]
    return es ? es.vlProgress : null
  }

  function appendVlScreenshot(eventId: number, screenshot: LiveScreenshot) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].vlScreenshots.push(screenshot)
  }

  function appendVlThought(eventId: number, thought: string) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].vlThoughts.push(thought)
  }

  function appendVlAction(eventId: number, action: any) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].vlActions.push(action)
  }

  return {
    state,
    selectedEvent,
    pendingApprovalCount,
    getEventLogs,
    getVlmAnalysis,
    getLiveScreenshot,
    getTriageResult,
    getHistoricalAnalysis,
    getAnalysisResult,
    ensureEphemeral,
    appendLog,
    setTriageResult,
    setHistoricalAnalysis,
    setAnalysisResult,
    setVlmAnalysis,
    setLiveScreenshot,
    addVlThought,
    addVlAction,
    setVlProgress,
    setEvents,
    selectEvent,
    updateEvent,
    getVlScreenshots,
    getVlThoughts,
    getVlActions,
    getVlProgress,
    appendVlScreenshot,
    appendVlThought,
    appendVlAction,
  }
}
