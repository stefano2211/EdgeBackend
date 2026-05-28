<script setup lang="ts">
/**
 * ConfidenceBadge — extracts confidence level from agent text via regex.
 * Renders a colored badge: Alto (green), Medio (yellow), Bajo (red).
 */

const props = defineProps<{
  text: string | null | undefined
}>()

function extractConfidence(text: string | null | undefined): { level: string; color: string } | null {
  if (!text) return null
  // Spanish pattern
  let match = text.match(/Nivel de confianza[:\s]*(Alto|Medio|Bajo)/i)
  if (match) {
    const level = match[1]
    const colors: Record<string, string> = {
      'Alto': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
      'Medio': 'bg-amber-500/10 text-amber-400 border-amber-500/30',
      'Bajo': 'bg-red-500/10 text-red-400 border-red-500/30',
    }
    return { level, color: colors[level] || 'bg-white/5 text-[#a0a0a0] border-white/10' }
  }
  // English pattern
  match = text.match(/Confidence level[:\s]*(High|Medium|Low)/i)
  if (match) {
    const level = match[1]
    const colors: Record<string, string> = {
      'High': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
      'Medium': 'bg-amber-500/10 text-amber-400 border-amber-500/30',
      'Low': 'bg-red-500/10 text-red-400 border-red-500/30',
    }
    return { level, color: colors[level] || 'bg-white/5 text-[#a0a0a0] border-white/10' }
  }
  return null
}

const confidence = extractConfidence(props.text)
</script>

<template>
  <span
    v-if="confidence"
    class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border"
    :class="confidence.color"
  >
    {{ confidence.level }} Confidence
  </span>
</template>
