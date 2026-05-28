<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  content: string
}>()

const isExpanded = ref(false)
</script>

<template>
  <div class="reasoning-block mb-3 rounded-lg border border-white/[0.06] bg-white/[0.02] overflow-hidden">
    <button
      @click="isExpanded = !isExpanded"
      class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/[0.03] transition-colors"
    >
      <!-- Brain icon -->
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="text-violet-400/70 flex-shrink-0"
      >
        <path d="M12 2a7 7 0 0 0-7 7c0 3 2 5 3 6.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-1.5C17 14 19 12 19 9a7 7 0 0 0-7-7Z"/>
        <path d="M9 22h6"/>
        <path d="M9 18h6"/>
      </svg>
      <span class="text-[11px] font-medium text-white/40 font-mono tracking-wide uppercase">Razonamiento</span>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="ml-auto text-white/20 transition-transform duration-200"
        :class="{ 'rotate-180': isExpanded }"
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
    <transition name="reasoning-expand">
      <div v-if="isExpanded" class="px-3 pb-3 pt-1">
        <div class="text-[12px] leading-[1.7] text-white/35 whitespace-pre-wrap font-mono border-l-2 border-violet-500/20 pl-3">{{ content }}</div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.reasoning-expand-enter-active,
.reasoning-expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.reasoning-expand-enter-from,
.reasoning-expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.reasoning-expand-enter-to,
.reasoning-expand-leave-from {
  max-height: 2000px;
}
</style>
