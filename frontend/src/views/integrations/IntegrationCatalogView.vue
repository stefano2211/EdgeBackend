<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import integrationService, { type IntegrationCatalog, type IntegrationInstance } from '@/services/integrationService'
import IntegrationSetupModal from './IntegrationSetupModal.vue'

const router = useRouter()
const catalog = ref<IntegrationCatalog[]>([])
const instances = ref<IntegrationInstance[]>([])
const isLoading = ref(true)
const selectedCatalog = ref<IntegrationCatalog | null>(null)
const showSetupModal = ref(false)

const CATEGORY_ICONS: Record<string, string> = {
  development: 'M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22',
  communication: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z',
  database: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z',
  cloud: 'M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z',
  productivity: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8',
}

const CATEGORY_COLORS: Record<string, string> = {
  development: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  communication: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  database: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  cloud: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
  productivity: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
}

const CATEGORY_LABELS: Record<string, string> = {
  development: 'Desarrollo',
  communication: 'Comunicación',
  database: 'Base de datos',
  cloud: 'Nube',
  productivity: 'Productividad',
}

const SOURCE_TYPE_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  official: { label: 'Oficial', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  custom: { label: 'Custom', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
}

const officialItems = computed(() => catalog.value.filter(i => i.source_type === 'official'))
const customItems = computed(() => catalog.value.filter(i => i.source_type === 'custom'))

const instanceCountBySlug = computed(() => {
  const map: Record<string, number> = {}
  for (const inst of instances.value) {
    if (inst.catalog) {
      map[inst.catalog.slug] = (map[inst.catalog.slug] || 0) + 1
    }
  }
  return map
})

async function loadData() {
  isLoading.value = true
  try {
    const [catalogRes, instancesRes] = await Promise.all([
      integrationService.listCatalog(),
      integrationService.listInstances(),
    ])
    catalog.value = catalogRes
    instances.value = instancesRes
  } catch (e) {
    console.error('Failed to load catalog', e)
  } finally {
    isLoading.value = false
  }
}

function configure(item: IntegrationCatalog) {
  selectedCatalog.value = item
  showSetupModal.value = true
}

function handleInstanceCreated() {
  showSetupModal.value = false
  selectedCatalog.value = null
  loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="px-6 py-6 max-w-6xl mx-auto space-y-10 h-full overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="mb-6">
      <h2 class="text-2xl font-bold text-white tracking-tight">Catálogo de Integraciones</h2>
      <p class="text-[#7a7a7a] text-sm mt-1">Conecta servicios de terceros para extender las capacidades del agente.</p>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="py-20 text-center">
      <svg class="animate-spin w-8 h-8 text-violet-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="text-[#7a7a7a]">Cargando catálogo...</p>
    </div>

    <template v-else>
      <!-- ── SECTION: MCP OFICIALES ── -->
      <section>
        <div class="flex items-center gap-3 mb-5">
          <div class="w-2 h-2 rounded-full bg-blue-400"></div>
          <h3 class="text-[13px] font-bold text-blue-400 uppercase tracking-widest">MCP Oficiales</h3>
          <span class="text-[11px] text-[#4a4a4a]">{{ officialItems.length }} disponibles</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div
            v-for="item in officialItems"
            :key="item.slug"
            class="group relative bg-[#2f2f2f]/30 border border-white/[0.06] rounded-2xl p-5 hover:border-blue-500/30 hover:bg-[#2f2f2f]/50 transition-all cursor-pointer overflow-hidden backdrop-blur-sm"
          >
            <div class="absolute -right-4 -top-4 w-24 h-24 bg-blue-600/5 rounded-full blur-3xl group-hover:bg-blue-600/10 transition-all"></div>

            <div v-if="instanceCountBySlug[item.slug]" class="absolute top-4 right-4">
              <span class="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase rounded border border-emerald-500/20">
                {{ instanceCountBySlug[item.slug] }} activa{{ instanceCountBySlug[item.slug] > 1 ? 's' : '' }}
              </span>
            </div>

            <div class="flex flex-col h-full">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center border mb-3"
                :class="CATEGORY_COLORS[item.category || 'productivity']"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path :d="CATEGORY_ICONS[item.category || 'productivity']"/>
                </svg>
              </div>

              <h3 class="text-base font-semibold text-white mb-1 group-hover:text-blue-400 transition-colors">{{ item.name }}</h3>
              <p class="text-[12px] text-[#7a7a7a] line-clamp-2 mb-3 flex-1">{{ item.description }}</p>

              <div class="mt-auto flex items-center justify-between">
                <span class="text-[10px] font-bold uppercase tracking-widest text-[#4a4a4a]">
                  {{ CATEGORY_LABELS[item.category || 'productivity'] }}
                </span>
                <span class="text-[10px] font-bold uppercase tracking-wider text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                  {{ SOURCE_TYPE_CONFIG[item.source_type]?.label || item.source_type }}
                </span>
              </div>

              <button
                @click.stop="configure(item)"
                class="mt-3 w-full py-2 bg-blue-600 hover:bg-blue-500 text-white text-[12px] font-medium rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
                {{ instanceCountBySlug[item.slug] ? 'Nueva instancia' : 'Configurar' }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ── SECTION: MCP CUSTOM ── -->
      <section v-if="customItems.length > 0">
        <div class="flex items-center gap-3 mb-5">
          <div class="w-2 h-2 rounded-full bg-amber-400"></div>
          <h3 class="text-[13px] font-bold text-amber-400 uppercase tracking-widest">MCP Custom</h3>
          <span class="text-[11px] text-[#4a4a4a]">{{ customItems.length }} disponible{{ customItems.length > 1 ? 's' : '' }}</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div
            v-for="item in customItems"
            :key="item.slug"
            class="group relative bg-[#2f2f2f]/30 border border-white/[0.06] rounded-2xl p-5 hover:border-amber-500/30 hover:bg-[#2f2f2f]/50 transition-all cursor-pointer overflow-hidden backdrop-blur-sm"
          >
            <div class="absolute -right-4 -top-4 w-24 h-24 bg-amber-600/5 rounded-full blur-3xl group-hover:bg-amber-600/10 transition-all"></div>

            <div v-if="instanceCountBySlug[item.slug]" class="absolute top-4 right-4">
              <span class="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase rounded border border-emerald-500/20">
                {{ instanceCountBySlug[item.slug] }} activa{{ instanceCountBySlug[item.slug] > 1 ? 's' : '' }}
              </span>
            </div>

            <div class="flex flex-col h-full">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center border mb-3"
                :class="CATEGORY_COLORS[item.category || 'productivity']"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path :d="CATEGORY_ICONS[item.category || 'productivity']"/>
                </svg>
              </div>

              <h3 class="text-base font-semibold text-white mb-1 group-hover:text-amber-400 transition-colors">{{ item.name }}</h3>
              <p class="text-[12px] text-[#7a7a7a] line-clamp-2 mb-3 flex-1">{{ item.description }}</p>

              <div class="mt-auto flex items-center justify-between">
                <span class="text-[10px] font-bold uppercase tracking-widest text-[#4a4a4a]">
                  {{ CATEGORY_LABELS[item.category || 'productivity'] }}
                </span>
                <span class="text-[10px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                  {{ SOURCE_TYPE_CONFIG[item.source_type]?.label || item.source_type }}
                </span>
              </div>

              <button
                @click.stop="configure(item)"
                class="mt-3 w-full py-2 bg-amber-600 hover:bg-amber-500 text-white text-[12px] font-medium rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-amber-600/20"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
                {{ instanceCountBySlug[item.slug] ? 'Nueva instancia' : 'Configurar' }}
              </button>
            </div>
          </div>
        </div>
      </section>


    </template>

    <!-- Setup Modal -->
    <IntegrationSetupModal
      v-if="selectedCatalog"
      :catalog="selectedCatalog"
      :show="showSetupModal"
      @close="showSetupModal = false; selectedCatalog = null"
      @created="handleInstanceCreated"
    />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.1); }
</style>
