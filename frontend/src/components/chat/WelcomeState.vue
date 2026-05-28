<script setup lang="ts">
import { ref, inject, onMounted, type Ref } from 'vue'
import promptService from '@/services/promptService'

const emit = defineEmits<{
  (e: 'select', query: string): void
}>()

const userName = inject<Ref<string>>('userName', ref(''))
const suggestions = ref<any[]>([])

const defaultSuggestions = [
  {
    title: 'Give me ideas',
    description: "for what to do with my kids' art",
    query: "Give me ideas for what to do with my kids' art"
  },
  {
    title: 'Explain options trading',
    description: "if I'm familiar with buying and selling stocks",
    query: "Explain options trading if I'm familiar with buying and selling stocks"
  },
  {
    title: 'Help me study',
    description: "vocabulary for a college entrance exam",
    query: "Help me study vocabulary for a college entrance exam"
  }
]

onMounted(async () => {
  try {
    const fetchedPrompts = await promptService.listPrompts(true)
    if (fetchedPrompts.length > 0) {
      suggestions.value = fetchedPrompts.map(p => ({
        title: p.title,
        description: p.description,
        query: p.query,
      }))
    } else {
      suggestions.value = defaultSuggestions
    }
  } catch (error) {
    console.warn('Failed to fetch prompts, falling back to defaults:', error)
    suggestions.value = defaultSuggestions
  }
})
</script>

<template>
  <div class="flex-1 flex flex-col items-center justify-center px-4 pt-8 pb-36 overflow-y-auto w-full">
    <!-- Welcome Header -->
    <div class="flex flex-col items-center gap-5 mb-14 animate-in">
      <div class="w-16 h-16 bg-white text-black font-bold rounded-full flex items-center justify-center text-2xl shadow-lg">
        OI
      </div>
      <h2 class="text-[28px] font-medium text-white">
        Hello, {{ userName || 'there' }}
      </h2>
    </div>
    
    <!-- Suggestions -->
    <div class="w-full max-w-2xl animate-in delay-150">
      <div class="flex items-center gap-2 mb-5 px-1">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#7a7a7a]"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>
        <span class="text-[13px] font-medium text-[#7a7a7a]">Suggested</span>
      </div>

      <div class="space-y-1">
        <button 
          v-for="(suggestion, index) in suggestions" 
          :key="index"
          @click="emit('select', suggestion.query)"
          class="w-full text-left px-4 py-3 rounded-xl hover:bg-white/[0.04] transition-all group cursor-pointer"
        >
          <div class="text-[15px] font-medium text-[#ececec] group-hover:text-white transition-colors">
            {{ suggestion.title }}
          </div>
          <div class="text-[13px] text-[#7a7a7a] mt-0.5">{{ suggestion.description }}</div>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-in {
  animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
.delay-150 {
  animation-delay: 150ms;
  animation-fill-mode: both;
}
</style>
