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

  function ensureEphemeral(eventId: number) {
    if (!ephemeralState[eventId]) {
      ephemeralState[eventId] = {
        logs: [],

      }
    }
  }

  function appendLog(eventId: number, log: LogLine) {
    ensureEphemeral(eventId)
    ephemeralState[eventId].logs.push(log)
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
    ensureEphemeral,
    appendLog,

    setEvents,
    selectEvent,
    updateEvent,

  }
}
