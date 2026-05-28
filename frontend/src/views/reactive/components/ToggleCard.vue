<script setup lang="ts">
defineProps<{
  icon: string
  title: string
  description: string
  meta: string
  isEnabled: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle', enabled: boolean): void
}>()
</script>

<template>
  <div class="bg-[#111] rounded-xl border border-white/[0.08] p-5 transition-all hover:border-purple-500/30 group">
    <div class="flex items-start justify-between mb-3">
      <div class="flex items-center gap-2">
        <span class="text-lg">{{ icon }}</span>
        <h3 class="text-[14px] font-semibold text-[#ececec]">{{ title }}</h3>
      </div>

      <!-- Toggle Switch -->
      <button
        @click="emit('toggle', !isEnabled)"
        class="relative w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none"
        :class="isEnabled ? 'bg-purple-500' : 'bg-white/10'"
      >
        <span
          class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200"
          :class="isEnabled ? 'translate-x-5' : 'translate-x-0'"
        />
      </button>
    </div>

    <p class="text-[12px] text-[#7a7a7a] mb-3 line-clamp-2">{{ description || 'Sin descripción' }}</p>

    <div class="flex items-center gap-2 text-[11px] text-[#555]">
      <span class="px-1.5 py-0.5 rounded bg-white/5 border border-white/[0.06]">{{ meta || 'Sin fuente' }}</span>
    </div>
  </div>
</template>
