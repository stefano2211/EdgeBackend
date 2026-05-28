<script setup lang="ts">
/**
 * SeverityBar — visual bar for OpenTelemetry severity scale (1-24).
 * Colors: debug (green), info (blue), warning (yellow), error (orange), critical (red).
 */

const props = defineProps<{
  number: number
}>()

const percentage = Math.min(Math.max((props.number / 24) * 100, 0), 100)

function getColorClass(num: number): string {
  if (num <= 8) return 'bg-emerald-500'
  if (num <= 12) return 'bg-blue-500'
  if (num <= 16) return 'bg-yellow-500'
  if (num <= 20) return 'bg-orange-500'
  return 'bg-red-500'
}

function getLabel(num: number): string {
  if (num <= 4) return 'TRACE'
  if (num <= 8) return 'DEBUG'
  if (num <= 12) return 'INFO'
  if (num <= 16) return 'WARN'
  if (num <= 20) return 'ERROR'
  return 'FATAL'
}

const colorClass = getColorClass(props.number)
const label = getLabel(props.number)
</script>

<template>
  <div class="flex items-center gap-2">
    <div class="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
      <div
        class="h-full rounded-full transition-all duration-500"
        :class="colorClass"
        :style="`width: ${percentage}%`"
      ></div>
    </div>
    <span class="text-[10px] text-[#7a7a7a] font-mono whitespace-nowrap">
      {{ number }}/24 ({{ label }})
    </span>
  </div>
</template>
