<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { knowledgeService, type KnowledgeBase } from '@/services/knowledgeService'
import ToggleCard from './components/ToggleCard.vue'

const router = useRouter()
const items = ref<KnowledgeBase[]>([])
const loading = ref(false)

const enabledCount = computed(() => items.value.filter(k => k.is_enabled_reactive).length)

async function load() {
  loading.value = true
  try {
    items.value = await knowledgeService.listKnowledgeBases()
  } catch (e) {
    console.error('Failed to load knowledge bases', e)
  } finally {
    loading.value = false
  }
}

async function toggleKb(id: string, enabled: boolean) {
  try {
    await knowledgeService.toggleReactive(id, enabled)
    const item = items.value.find(k => k.id === id)
    if (item) item.is_enabled_reactive = enabled
  } catch (e) {
    console.error('Failed to toggle KB', e)
  }
}

function getIconForKb(kb: KnowledgeBase): string {
  const name = kb.name.toLowerCase()
  if (name.includes('sop')) return '📋'
  if (name.includes('manual')) return '📖'
  if (name.includes('spec')) return '📐'
  return '📚'
}

onMounted(load)
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <header class="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
      <div>
        <h2 class="text-[16px] font-semibold text-white">Bases de Conocimiento Reactivas</h2>
        <p class="text-[12px] text-[#7a7a7a] mt-0.5">Activa las bases de conocimiento que el sistema de eventos podrá consultar</p>
      </div>
      <div class="flex items-center gap-4">
        <div class="text-[12px] text-purple-400 font-mono">
          {{ enabledCount }}/{{ items.length }} activas
        </div>
        <button
          @click="router.push('/events')"
          class="px-3 py-1.5 rounded-lg text-[12px] bg-purple-500/15 text-purple-300 border border-purple-500/20 hover:bg-purple-500/25 transition-colors"
        >
          Volver a Eventos
        </button>
      </div>
    </header>

    <div class="flex-1 overflow-y-auto px-6 py-5">
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="i in 3" :key="i" class="h-32 bg-white/5 rounded-xl animate-pulse" />
      </div>

      <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center h-full text-[#7a7a7a]">
        <span class="text-4xl mb-3">📚</span>
        <p class="text-[14px]">No hay bases de conocimiento</p>
        <p class="text-[12px] mt-1">Ve a Workspace &gt; Knowledge para crear una</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ToggleCard
          v-for="item in items"
          :key="item.id"
          :icon="getIconForKb(item)"
          :title="item.name"
          :description="item.description || 'Sin descripción'"
          :meta="item.is_enabled_chat ? 'Chat + Reactive' : 'Reactive only'"
          :is-enabled="item.is_enabled_reactive"
          @toggle="toggleKb(item.id, $event)"
        />
      </div>
    </div>
  </div>
</template>
