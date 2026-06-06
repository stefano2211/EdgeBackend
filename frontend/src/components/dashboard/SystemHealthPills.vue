<script setup lang="ts">
interface Props {
  llmStatus: string
  systemStatus: string
  activeIntegrations: number
  activeKnowledgeBases: number
  activeDbConnections: number
}

defineProps<Props>()
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <!-- LLM -->
    <div
      class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-medium"
      :class="llmStatus === 'healthy'
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'"
    >
      <span class="w-1.5 h-1.5 rounded-full" :class="llmStatus === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'"></span>
      {{ llmStatus === 'healthy' ? 'LLM Online' : 'LLM Offline' }}
    </div>

    <!-- System -->
    <div
      class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-medium"
      :class="systemStatus === 'operational'
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
        : 'bg-red-500/10 text-red-400 border-red-500/20'"
    >
      <span class="w-1.5 h-1.5 rounded-full" :class="systemStatus === 'operational' ? 'bg-emerald-400' : 'bg-red-400'"></span>
      {{ systemStatus === 'operational' ? 'Sistema Operativo' : 'Sistema Degradado' }}
    </div>

    <!-- Integraciones -->
    <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border bg-white/5 text-[#a0a0a0] border-white/10 text-[11px] font-medium">
      <span class="text-white font-semibold">{{ activeIntegrations }}</span> Integraciones
    </div>

    <!-- KBs -->
    <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border bg-white/5 text-[#a0a0a0] border-white/10 text-[11px] font-medium">
      <span class="text-white font-semibold">{{ activeKnowledgeBases }}</span> Bases de Conocimiento
    </div>

    <!-- DBs -->
    <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border bg-white/5 text-[#a0a0a0] border-white/10 text-[11px] font-medium">
      <span class="text-white font-semibold">{{ activeDbConnections }}</span> Bases de Datos
    </div>
  </div>
</template>
