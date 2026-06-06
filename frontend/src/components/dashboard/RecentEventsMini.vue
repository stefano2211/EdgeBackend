<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { RecentEventItem } from '@/services/dashboardService'

const props = defineProps<{
  events: RecentEventItem[]
}>()

const router = useRouter()

function severityClasses(s: string) {
  switch (s) {
    case 'critical': return 'bg-red-500/10 text-red-400 border-red-500/20'
    case 'error': return 'bg-orange-500/10 text-orange-400 border-orange-500/20'
    case 'warning': return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    case 'info': return 'bg-blue-500/10 text-blue-400 border-blue-500/20'
    case 'debug': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    default: return 'bg-white/5 text-[#a0a0a0] border-white/10'
  }
}

function statusDot(s: string) {
  switch (s) {
    case 'pending': return 'bg-gray-400'
    case 'analyzing': return 'bg-blue-400 animate-pulse'
    case 'awaiting_approval': return 'bg-amber-400'
    case 'executing': return 'bg-purple-400 animate-pulse'
    case 'completed': return 'bg-emerald-400'
    case 'failed': return 'bg-red-400'
    default: return 'bg-gray-600'
  }
}

function formatDate(d: string) {
  return new Date(d).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function goToEvents() {
  router.push('/events')
}
</script>

<template>
  <div class="bg-[#111] border border-white/[0.08] rounded-xl p-4 h-full flex flex-col">
    <div class="flex items-center justify-between mb-3">
      <div class="text-[11px] text-[#7a7a7a] uppercase tracking-wider font-medium">Eventos Recientes</div>
      <button @click="goToEvents" class="text-[11px] text-[#7a7a7a] hover:text-white transition-colors">
        Ver todos →
      </button>
    </div>

    <div class="flex-1 overflow-auto">
      <div v-if="events.length === 0" class="text-center py-8 text-[#555] text-sm">
        Sin eventos recientes
      </div>
      <div v-else class="space-y-1">
        <div
          v-for="ev in events"
          :key="ev.id"
          @click="goToEvents"
          class="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.04] cursor-pointer transition-colors group"
        >
          <div class="w-2 h-2 rounded-full shrink-0" :class="statusDot(ev.status)"></div>
          <div class="flex-1 min-w-0">
            <div class="text-[13px] text-[#ececec] truncate font-medium">{{ ev.title }}</div>
            <div class="flex items-center gap-2 mt-0.5">
              <span :class="['px-1.5 py-[1px] rounded text-[10px] font-bold uppercase border', severityClasses(ev.severity_text)]">
                {{ ev.severity_text }}
              </span>
              <span class="text-[11px] text-[#555]">{{ ev.source }}</span>
            </div>
          </div>
          <div class="text-[11px] text-[#555] shrink-0">{{ formatDate(ev.created_at) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
