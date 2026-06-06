<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: Record<string, number>
}>()

const severityOrder = ['critical', 'error', 'warning', 'info', 'debug']
const severityColors: Record<string, string> = {
  critical: '#ef4444',
  error: '#f97316',
  warning: '#eab308',
  info: '#3b82f6',
  debug: '#10b981',
}

const chartSeries = computed(() => {
  return severityOrder
    .filter((s) => (props.data[s] || 0) > 0)
    .map((s) => props.data[s] || 0)
})

const chartLabels = computed(() => {
  return severityOrder.filter((s) => (props.data[s] || 0) > 0).map((s) => s.toUpperCase())
})

const chartColors = computed(() => {
  return severityOrder.filter((s) => (props.data[s] || 0) > 0).map((s) => severityColors[s])
})

const chartOptions = computed(() => ({
  chart: {
    type: 'donut',
    background: 'transparent',
    fontFamily: 'inherit',
  },
  theme: { mode: 'dark' },
  labels: chartLabels.value,
  colors: chartColors.value,
  plotOptions: {
    pie: {
      donut: {
        size: '65%',
        labels: {
          show: true,
          name: { show: true, fontSize: '10px', color: '#a0a0a0' },
          value: { show: true, fontSize: '18px', fontWeight: 600, color: '#ececec' },
          total: {
            show: true,
            showAlways: true,
            label: 'TOTAL',
            fontSize: '10px',
            fontWeight: 400,
            color: '#7a7a7a',
            formatter: () =>
              String(chartSeries.value.reduce((a, b) => a + b, 0)),
          },
        },
      },
    },
  },
  dataLabels: { enabled: false },
  legend: {
    position: 'bottom',
    fontSize: '11px',
    labels: { colors: '#a0a0a0' },
    markers: { size: 6, shape: 'circle' },
    itemMargin: { horizontal: 8, vertical: 2 },
  },
  stroke: { show: true, colors: ['#111'], width: 2 },
  tooltip: {
    theme: 'dark',
    y: { formatter: (val: number) => `${val} eventos` },
  },
}))
</script>

<template>
  <div class="bg-[#111] border border-white/[0.08] rounded-xl p-4 h-full flex flex-col">
    <div class="text-[11px] text-[#7a7a7a] uppercase tracking-wider font-medium mb-3">Severidad (7d)</div>
    <div class="flex-1 min-h-[200px]">
      <apexchart
        v-if="chartSeries.length > 0"
        type="donut"
        height="220"
        :options="chartOptions"
        :series="chartSeries"
      />
      <div v-else class="h-full flex items-center justify-center text-[#555] text-sm">
        Sin datos
      </div>
    </div>
  </div>
</template>
