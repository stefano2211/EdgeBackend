<script setup lang="ts">
/**
 * DynamicMetricCard — renders any key-value from event.body dynamically.
 * No hardcoded fields. Adapts to the data type (number, string, boolean, object).
 */

const props = defineProps<{
  label: string
  value: any
}>()

function inferUnit(key: string): string {
  const lower = key.toLowerCase()
  if (lower.includes('temp') || lower.includes('_c')) return '°C'
  if (lower.includes('psi')) return 'PSI'
  if (lower.includes('ppm')) return 'PPM'
  if (lower.includes('ms')) return 'ms'
  if (lower.includes('_pct') || lower.includes('percentage') || lower.includes('percent')) return '%'
  if (lower.includes('_count') || lower.includes('count')) return 'count'
  if (lower.includes('_bytes') || lower.includes('bytes')) return 'B'
  if (lower.includes('_mb')) return 'MB'
  if (lower.includes('_gb')) return 'GB'
  if (lower.includes('_kbps') || lower.includes('kbps')) return 'Kbps'
  if (lower.includes('_mbps') || lower.includes('mbps')) return 'Mbps'
  return ''
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return value.toString()
    return value.toFixed(2)
  }
  if (typeof value === 'string') {
    // ISO date detection
    if (/^\d{4}-\d{2}-\d{2}T/.test(value)) {
      const d = new Date(value)
      if (!isNaN(d.getTime())) return d.toLocaleString()
    }
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return 'Empty'
    return `${value.length} items`
  }
  return JSON.stringify(value)
}

const isNumber = typeof props.value === 'number'
const unit = isNumber ? inferUnit(props.label) : ''
const displayValue = formatValue(props.value)
</script>

<template>
  <div
    class="bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 hover:border-white/[0.15] transition-colors"
    :class="isNumber ? 'min-w-[120px]' : ''"
  >
    <div class="text-[10px] text-[#7a7a7a] uppercase tracking-wider font-semibold mb-1 truncate">
      {{ label.replace(/_/g, ' ') }}
    </div>
    <div class="flex items-baseline gap-1">
      <span
        class="font-mono font-semibold text-[#ececec]"
        :class="isNumber ? 'text-[18px]' : 'text-[13px]'"
      >
        {{ displayValue }}
      </span>
      <span v-if="unit" class="text-[11px] text-[#7a7a7a]">{{ unit }}</span>
    </div>
  </div>
</template>
