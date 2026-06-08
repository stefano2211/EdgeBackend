<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getDashboardSummary, type DashboardSummary } from '@/services/dashboardService'
import KpiCard from '@/components/dashboard/KpiCard.vue'
import SeverityDonut from '@/components/dashboard/SeverityDonut.vue'
import RecentEventsMini from '@/components/dashboard/RecentEventsMini.vue'
import SystemHealthPills from '@/components/dashboard/SystemHealthPills.vue'

const summary = ref<DashboardSummary | null>(null)
const isLoading = ref(false)
const error = ref('')

  async function load() {
  isLoading.value = true
  error.value = ''
  try {
    summary.value = await getDashboardSummary()
  } catch (e: any) {
    const backendMsg = e?.response?.data?.detail
    error.value = backendMsg || 'No se pudo cargar el dashboard.'
    console.error('Dashboard load error:', e)
  } finally {
    isLoading.value = false
  }
}

function fmtDuration(seconds: number | null) {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.round(seconds / 60)}m`
}

onMounted(load)
</script>

<template>
  <div class="h-full overflow-auto">
    <div class="p-6 space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-[18px] font-semibold text-white tracking-tight">Dashboard</h1>
          <p class="text-[12px] text-[#7a7a7a] mt-0.5">
            Resumen operativo de Aura AI
          </p>
        </div>
        <button
          @click="load"
          :disabled="isLoading"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-[12px] text-[#b4b4b4] hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="isLoading && 'animate-spin'"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>
          Refrescar
        </button>
      </div>

      <!-- Error -->
      <div v-if="error" class="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-[12px] text-red-300">
        {{ error }}
      </div>

      <!-- Loading skeleton -->
      <template v-if="isLoading && !summary">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div v-for="i in 4" :key="i" class="bg-[#111] border border-white/[0.06] rounded-xl p-4 h-[76px] animate-pulse" />
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="bg-[#111] border border-white/[0.06] rounded-xl p-4 h-[280px] animate-pulse" />
          <div class="lg:col-span-2 bg-[#111] border border-white/[0.06] rounded-xl p-4 h-[280px] animate-pulse" />
        </div>
      </template>

      <!-- Content -->
      <template v-if="summary">
        <!-- KPI Row -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Eventos (24h)"
            :value="summary.total_events_24h"
            color="blue"
            iconPath="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5"
          />
          <KpiCard
            label="Críticos Pendientes"
            :value="summary.critical_pending"
            color="red"
            iconPath="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"
          />
          <KpiCard
            label="MTTR Promedio"
            :value="fmtDuration(summary.avg_ttr_seconds)"
            color="emerald"
            iconPath="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
          />
          <KpiCard
            label="Falsos Positivos"
            :value="`${Math.round(summary.false_positive_rate * 100)}%`"
            color="amber"
            iconPath="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"
          />
        </div>

        <!-- Middle Row: Donut + Recent Events -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <SeverityDonut :data="summary.events_by_severity" />
          <RecentEventsMini :events="summary.recent_events" class="lg:col-span-2" />
        </div>

        <!-- Bottom Row: System Health + Extra KPIs -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="bg-[#111] border border-white/[0.08] rounded-xl p-4">
            <div class="text-[11px] text-[#7a7a7a] uppercase tracking-wider font-medium mb-3">Estado del Sistema</div>
            <SystemHealthPills
              :llm-status="summary.llm_status"
              :system-status="summary.system_status"
              :active-integrations="summary.active_integrations"
              :active-knowledge-bases="summary.active_knowledge_bases"
              :active-db-connections="summary.active_db_connections"
            />
          </div>

          <div class="bg-[#111] border border-white/[0.08] rounded-xl p-4">
            <div class="text-[11px] text-[#7a7a7a] uppercase tracking-wider font-medium mb-3">Métricas AIOps (7d)</div>
            <div class="grid grid-cols-2 gap-3">
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[#555]">Resueltos Auto</span>
                <span class="text-[18px] font-semibold text-emerald-400">{{ summary.events_auto_resolved }}</span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[#555]">Fallidos</span>
                <span class="text-[18px] font-semibold text-red-400">{{ summary.events_failed }}</span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[#555]">MTTD</span>
                <span class="text-[18px] font-semibold text-white">{{ fmtDuration(summary.avg_ttd_seconds) }}</span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[#555]">Total (7d)</span>
                <span class="text-[18px] font-semibold text-white">{{ summary.total_events_7d }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
