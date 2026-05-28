import api from './api'

export type EventSeverityText = 'critical' | 'error' | 'warning' | 'info' | 'debug'
export type EventStatus =
  | 'pending'
  | 'analyzing'
  | 'awaiting_approval'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'suppressed'

export interface LogLine {
  timestamp: string
  level: 'info' | 'debug' | 'error' | 'warn'
  message: string
}

export interface AuraEvent {
  id: number
  event_id: string
  event_type: string
  source: string
  timestamp: string
  subject?: string
  severity_number: number
  severity_text: EventSeverityText
  title: string
  description?: string
  body?: Record<string, any>
  domain?: string
  subdomain?: string
  correlation_id?: string
  dedup_key?: string
  resource?: Record<string, any>
  status: EventStatus
  suppression_reason?: string
  agent_analysis?: string
  agent_diagnosis?: string
  agent_plan?: string
  actions_taken?: any[]
  created_at: string
  updated_at: string
  resolved_at?: string
  triggered_by_user_id?: number
  correlation_group_id?: number

  // Ephemeral fields (received via SSE)
  processing_log?: LogLine[]
}

export interface EventListResponse {
  total: number
  items: AuraEvent[]
}

export interface EventFilters {
  severity_text?: EventSeverityText
  status?: EventStatus
  domain?: string
  event_type?: string
  source?: string
  limit?: number
  offset?: number
}

export interface ApprovalPayload {
  notes?: string
}

export interface EventFeedbackPayload {
  feedback_type: 'false_positive' | 'incorrect_diagnosis' | 'wrong_severity' | 'other'
  comment?: string
}

// ═══════════════════════════════════════════════════════════════════════════════
//  DEMO PRESETS — Quick-trigger test payloads sent via webhook
// ═══════════════════════════════════════════════════════════════════════════════

export interface DemoPreset {
  id: string
  label: string
  icon: string
  severity_text: EventSeverityText
  title: string
  description: string
  data: Record<string, any>
}

export const DEMO_PRESETS: DemoPreset[] = [
  {
    id: 'boiler_pressure',
    label: 'Sobrepresión de Caldera',
    icon: '🔴',
    severity_text: 'critical',
    title: 'Presión de caldera excede límite operacional (PSI > 320)',
    description: 'El sensor PT-4401 en la caldera principal reporta lecturas de 327 PSI, superando el umbral crítico de 320 PSI. Se recomienda reducción inmediata de carga térmica.',
    data: {
      sensor_id: 'PT-4401',
      value: 327.4,
      unit: 'PSI',
      threshold: 320,
      location: 'Boiler Room A — Main Steam Header',
      timestamp: new Date().toISOString(),
    },
  },
  {
    id: 'coolant_flow',
    label: 'Flujo de Refrigerante',
    icon: '🟠',
    severity_text: 'warning',
    title: 'Anomalía en tasa de flujo de refrigerante — Línea 2',
    description: 'Desviación del 18% en la tasa de flujo de refrigerante respecto al baseline histórico de 30 días.',
    data: {
      metric: 'coolant_flow_rate',
      current_value: 42.3,
      baseline_avg: 51.6,
      deviation_pct: -18.0,
      unit: 'L/min',
      line: 'Production Line 2',
      collector: 'db_collector_postgres_historian',
    },
  },
  {
    id: 'compressor_vibration',
    label: 'Vibración de Compresor',
    icon: '🟡',
    severity_text: 'warning',
    title: 'Vibración elevada en motor de compresor MC-101',
    description: 'Sensor de vibración VS-101 reporta 8.2 mm/s RMS, superando el umbral de alerta de 7.1 mm/s.',
    data: {
      sensor_id: 'VS-101',
      value: 8.2,
      unit: 'mm/s RMS',
      threshold_alert: 7.1,
      threshold_critical: 11.0,
      equipment: 'Compressor Motor MC-101',
      location: 'Compressor House — Bay 3',
    },
  },
  {
    id: 'ph_calibration',
    label: 'Calibración de pH',
    icon: '🟢',
    severity_text: 'info',
    title: 'Verificación rutinaria de calibración — Sensor de pH',
    description: 'Operador solicita verificación de calibración del sensor de pH en torre de enfriamiento CT-01.',
    data: {
      sensor_id: 'pH-CT01',
      last_calibration: new Date(Date.now() - 30 * 86400000).toISOString(),
      current_reading: 7.2,
      expected_range: '7.0 - 7.5',
    },
  },
  {
    id: 'plc_comm_failure',
    label: 'Falla PLC',
    icon: '🔴',
    severity_text: 'warning',
    title: 'Falla de comunicación PLC — Estación de empaque EP-03',
    description: 'El PLC de la estación de empaque EP-03 perdió comunicación con el servidor OPC durante 45 segundos.',
    data: {
      plc_id: 'PLC-EP03',
      downtime_seconds: 45,
      opc_server: 'OPC-UA-MAIN',
      reconnect_attempts: 3,
      resolved: false,
    },
  },
  {
    id: 'h2s_gas',
    label: 'Detección de Gas H₂S',
    icon: '☠️',
    severity_text: 'critical',
    title: 'Detección de gas H₂S en zona de proceso — Alarma Nivel 2',
    description: 'Detector de gas GD-7701 detectó concentración de 12 ppm de H₂S, superando el límite TWA de 10 ppm.',
    data: {
      detector_id: 'GD-7701',
      gas: 'H2S',
      concentration_ppm: 12,
      limit_twa: 10,
      limit_stel: 15,
      location: 'Process Area — Desulfurization Unit',
      wind_direction: 'NNW',
      wind_speed_kmh: 8,
    },
  },
  {
    id: 'transformer_temp',
    label: 'Temperatura de Transformador',
    icon: '🟡',
    severity_text: 'warning',
    title: 'Temperatura anómala en transformador eléctrico TR-02',
    description: 'Sensor de temperatura TT-TR02 reporta 78°C en devanado primario, 8°C por encima del promedio operacional.',
    data: {
      sensor_id: 'TT-TR02',
      value: 78,
      unit: '°C',
      baseline_avg: 70,
      equipment: 'Power Transformer TR-02',
      location: 'Electrical Substation — Zone B',
    },
  },
  {
    id: 'send_gmail',
    label: 'Enviar Gmail de Prueba',
    icon: '📧',
    severity_text: 'warning',
    title: 'Send test Gmail from Aura AI',
    description: 'Enviar un correo electrónico de prueba para verificar conectividad de servicios de comunicación.',
    data: {
      task_type: 'email_automation',
      target_email: 'stefano.andres2004@gmail.com',
      subject: 'Test from Aura AI',
      body: 'This is an automated test email sent by the Aura AI event system.',
      service: 'Gmail',
    },
  },
]

// ═══════════════════════════════════════════════════════════════════════════════
//  SSE TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface SSEPayload {
  type: string
  data?: any
  event?: string
}

export interface LiveScreenshot {
  b64: string
  step: number
  action?: string
  click?: { x: number; y: number; type: string }
}

export type SSEHandler = (payload: SSEPayload) => void
export type SSEErrorHandler = (err: Event) => void

// ═══════════════════════════════════════════════════════════════════════════════
//  SERVICE
// ═══════════════════════════════════════════════════════════════════════════════

const eventService = {
  async listEvents(filters: EventFilters = {}): Promise<EventListResponse> {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== undefined && v !== null)
    )
    const res = await api.get('/api/v1/events', { params })
    return res.data
  },

  async getEvent(id: number): Promise<AuraEvent> {
    const res = await api.get(`/api/v1/events/${id}`)
    return res.data
  },

  async approveEvent(id: number, payload: ApprovalPayload = {}): Promise<AuraEvent> {
    const res = await api.post(`/api/v1/events/${id}/approve`, payload)
    return res.data
  },

  async rejectEvent(id: number, payload: ApprovalPayload = {}): Promise<AuraEvent> {
    const res = await api.post(`/api/v1/events/${id}/reject`, payload)
    return res.data
  },

  async submitFeedback(id: number, payload: EventFeedbackPayload): Promise<void> {
    await api.post(`/api/v1/events/${id}/feedback`, payload)
  },

  openSSEStream(
    onMessage: SSEHandler,
    onError?: SSEErrorHandler
  ): EventSource | null {
    const token = localStorage.getItem('token')
    if (!token) {
      console.warn('[SSE] No auth token found — skipping stream connection.')
      return null
    }
    const baseURL = import.meta.env.PROD ? (import.meta.env.VITE_API_URL || '') : ''
    const url = `${baseURL}/api/v1/events/stream`

    const es = new EventSource(`${url}?token=${token}`)
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        onMessage(data)
      } catch {
        // heartbeat or non-JSON frame — ignore
      }
    }
    if (onError) es.onerror = onError
    return es
  },
}

export default eventService
