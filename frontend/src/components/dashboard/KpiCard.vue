<script setup lang="ts">
interface Props {
  label: string
  value: string | number
  color?: string
  iconPath?: string
}
const props = withDefaults(defineProps<Props>(), {
  color: 'white',
  iconPath: 'M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5'
})

const colorMap: Record<string, { bg: string; text: string; ring: string }> = {
  red: { bg: 'bg-red-500/10', text: 'text-red-400', ring: 'ring-red-500/20' },
  orange: { bg: 'bg-orange-500/10', text: 'text-orange-400', ring: 'ring-orange-500/20' },
  amber: { bg: 'bg-amber-500/10', text: 'text-amber-400', ring: 'ring-amber-500/20' },
  emerald: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', ring: 'ring-emerald-500/20' },
  blue: { bg: 'bg-blue-500/10', text: 'text-blue-400', ring: 'ring-blue-500/20' },
  purple: { bg: 'bg-purple-500/10', text: 'text-purple-400', ring: 'ring-purple-500/20' },
  cyan: { bg: 'bg-cyan-500/10', text: 'text-cyan-400', ring: 'ring-cyan-500/20' },
  white: { bg: 'bg-white/5', text: 'text-white', ring: 'ring-white/10' },
}

function cc() {
  return colorMap[props.color || 'white'] || colorMap['white']
}
</script>

<template>
  <div class="bg-[#111] border border-white/[0.08] rounded-xl p-4 flex items-center gap-4 transition-colors hover:border-white/[0.12]">
    <div
      class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ring-1"
      :class="[cc().bg, cc().ring]"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="cc().text">
        <path :d="iconPath"/>
      </svg>
    </div>
    <div class="min-w-0">
      <div class="text-[11px] text-[#7a7a7a] uppercase tracking-wider font-medium">{{ label }}</div>
      <div class="text-[22px] font-semibold text-white tracking-tight truncate">{{ value }}</div>
    </div>
  </div>
</template>
