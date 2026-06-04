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

const searchQuery = ref('')
const selectedCategory = ref('all')

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

const CATEGORY_DOTS: Record<string, string> = {
  development: 'bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.5)]',
  communication: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]',
  database: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]',
  cloud: 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.5)]',
  productivity: 'bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.5)]',
}

const CATEGORY_RGBS: Record<string, string> = {
  development: '96, 165, 250',
  communication: '52, 211, 153',
  database: '251, 191, 36',
  cloud: '56, 189, 248',
  productivity: '167, 139, 250',
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

const categories = [
  { id: 'all', label: 'Todas' },
  { id: 'development', label: 'Desarrollo' },
  { id: 'communication', label: 'Comunicación' },
  { id: 'database', label: 'Bases de datos' },
  { id: 'cloud', label: 'Nube' },
  { id: 'productivity', label: 'Productividad' },
]

const categoryCount = computed(() => {
  const counts: Record<string, number> = { all: catalog.value.length }
  for (const item of catalog.value) {
    if (item.category) {
      counts[item.category] = (counts[item.category] || 0) + 1
    }
  }
  return counts
})

const filteredCatalog = computed(() => {
  return catalog.value.filter(item => {
    const matchesSearch =
      !searchQuery.value ||
      item.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      (item.description && item.description.toLowerCase().includes(searchQuery.value.toLowerCase()))
    
    const matchesCategory =
      selectedCategory.value === 'all' ||
      item.category === selectedCategory.value
      
    return matchesSearch && matchesCategory
  })
})

const officialItems = computed(() => filteredCatalog.value.filter(i => i.source_type === 'official'))
const customItems = computed(() => filteredCatalog.value.filter(i => i.source_type === 'custom'))

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

function resetFilters() {
  searchQuery.value = ''
  selectedCategory.value = 'all'
}

onMounted(loadData)
</script>

<template>
  <div class="px-6 py-6 max-w-6xl mx-auto space-y-8 h-full overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="relative overflow-hidden p-6 rounded-2xl border border-white/[0.04] bg-gradient-to-r from-white/[0.03] to-white/[0.01] backdrop-blur-md">
      <div class="absolute -left-12 -top-12 w-48 h-48 bg-blue-600/5 rounded-full blur-3xl"></div>
      <div class="absolute -right-12 -bottom-12 w-48 h-48 bg-violet-600/5 rounded-full blur-3xl"></div>
      
      <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 class="text-2xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-[#ececec] to-[#999999]">
            Catálogo de Integraciones
          </h2>
          <p class="text-[#7a7a7a] text-xs md:text-sm mt-1 max-w-xl">
            Conecta y administra servicios de terceros en la red de Model Context Protocol (MCP) para expandir las capacidades cognitivas del agente.
          </p>
        </div>
        <div class="flex items-center gap-3 self-start md:self-auto">
          <div class="flex flex-col items-end text-right">
            <span class="text-[11px] font-bold text-violet-400 uppercase tracking-widest">Protocolo MCP</span>
            <span class="text-[10px] text-[#7a7a7a] mt-0.5">Model Context Protocol</span>
          </div>
          <div class="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400 animate-pulse">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5"/>
            </svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="isLoading" class="space-y-8">
      <div class="flex flex-col md:flex-row gap-4 bg-white/[0.01] border border-white/[0.04] p-4 rounded-2xl animate-pulse">
        <div class="h-9 bg-white/5 rounded-xl flex-1 max-w-md"></div>
        <div class="flex gap-2 overflow-x-auto no-scrollbar">
          <div v-for="n in 6" :key="n" class="h-7 w-20 bg-white/5 rounded-full shrink-0"></div>
        </div>
      </div>
      
      <div class="space-y-4">
        <div class="h-4 w-28 bg-white/5 rounded animate-pulse"></div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div v-for="n in 3" :key="n" class="border border-white/[0.04] rounded-2xl p-5 bg-white/[0.01] space-y-4 animate-pulse">
            <div class="w-10 h-10 rounded-xl bg-white/5"></div>
            <div class="space-y-2">
              <div class="h-4 bg-white/5 rounded w-1/3"></div>
              <div class="h-3 bg-white/5 rounded w-5/6"></div>
              <div class="h-3 bg-white/5 rounded w-2/3"></div>
            </div>
            <div class="h-8 bg-white/5 rounded-xl w-full pt-4"></div>
          </div>
        </div>
      </div>
    </div>

    <template v-else>
      <!-- Filters & Search -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/[0.01] border border-white/[0.04] p-4 rounded-2xl backdrop-blur-md">
        <!-- Search -->
        <div class="relative flex-1 max-w-md">
          <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
            <svg class="h-4 w-4 text-[#7a7a7a]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Buscar por nombre o descripción..."
            class="w-full bg-[#111] border border-white/10 rounded-xl pl-9 pr-8 py-2 text-xs text-[#ececec] placeholder-[#555] focus:outline-none focus:border-white/20 focus:ring-1 focus:ring-white/10 transition-all duration-200"
          />
          <button
            v-if="searchQuery"
            @click="searchQuery = ''"
            class="absolute inset-y-0 right-0 pr-3 flex items-center text-[#7a7a7a] hover:text-white"
          >
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Categories Filter -->
        <div class="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">
          <button
            v-for="cat in categories"
            :key="cat.id"
            @click="selectedCategory = cat.id"
            class="text-[11px] font-bold uppercase tracking-wider px-3.5 py-1.5 rounded-full border transition-all duration-200 whitespace-nowrap flex items-center gap-1.5"
            :class="selectedCategory === cat.id
              ? 'bg-white text-black border-white shadow-lg shadow-white/5'
              : 'bg-white/[0.02] border-white/10 text-[#7a7a7a] hover:text-white hover:border-white/20'
            "
          >
            {{ cat.label }}
            <span class="text-[9px] px-1.5 py-0.5 rounded-full transition-colors font-semibold"
              :class="selectedCategory === cat.id
                ? 'bg-black/10 text-black'
                : 'bg-white/5 text-[#555]'
              "
            >
              {{ categoryCount[cat.id] || 0 }}
            </span>
          </button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="officialItems.length === 0 && customItems.length === 0" class="py-16 text-center border border-dashed border-white/10 rounded-2xl bg-white/[0.01] backdrop-blur-sm max-w-md mx-auto animate-in">
        <div class="w-12 h-12 rounded-full bg-white/[0.04] border border-white/10 flex items-center justify-center mx-auto mb-4">
          <svg class="w-5 h-5 text-[#7a7a7a]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <h4 class="text-sm font-semibold text-white mb-1">No se encontraron integraciones</h4>
        <p class="text-[12px] text-[#7a7a7a] max-w-[280px] mx-auto mb-4">Intenta cambiar la búsqueda o restablecer los filtros de categoría.</p>
        <button
          @click="resetFilters"
          class="px-4 py-2 bg-white text-black text-xs font-semibold rounded-lg hover:bg-[#ececec] transition-colors"
        >
          Restablecer filtros
        </button>
      </div>

      <!-- ── SECTION: MCP OFICIALES ── -->
      <section v-if="officialItems.length > 0" class="space-y-4 animate-in">
        <div class="flex items-center gap-3">
          <div class="w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.5)]"></div>
          <h3 class="text-[11px] font-extrabold text-[#7a7a7a] uppercase tracking-widest">MCP Oficiales</h3>
          <span class="text-[10px] text-[#4a4a4a] font-semibold">{{ officialItems.length }} disponibles</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div
            v-for="item in officialItems"
            :key="item.slug"
            @click="configure(item)"
            :style="`--glow-color: ${CATEGORY_RGBS[item.category || 'productivity'] || '167, 139, 250'}`"
            class="integration-card group relative bg-gradient-to-b from-white/[0.04] to-white/[0.01] border border-white/[0.06] rounded-2xl p-5 hover:border-white/15 hover:bg-white/[0.03] transition-all duration-300 hover:-translate-y-1.5 cursor-pointer overflow-hidden backdrop-blur-md"
          >
            <div class="absolute -right-4 -top-4 w-24 h-24 bg-white/[0.02] rounded-full blur-3xl group-hover:bg-white/[0.04] transition-all duration-500"></div>

            <div v-if="instanceCountBySlug[item.slug]" class="absolute top-4 right-4 flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
              <span class="relative flex h-1.5 w-1.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
              </span>
              <span class="text-emerald-400 text-[9px] font-bold uppercase tracking-wider">
                {{ instanceCountBySlug[item.slug] }} activa{{ (instanceCountBySlug[item.slug] || 0) > 1 ? 's' : '' }}
              </span>
            </div>

            <div class="flex flex-col h-full">
              <div class="w-11 h-11 rounded-xl flex items-center justify-center border transition-transform duration-500 group-hover:scale-110 mb-4"
                :class="CATEGORY_COLORS[item.category || 'productivity']"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path :d="CATEGORY_ICONS[item.category || 'productivity']"/>
                </svg>
              </div>

              <h3 class="text-sm font-semibold text-white mb-1.5 transition-colors">{{ item.name }}</h3>
              <p class="text-[12px] text-[#7a7a7a] leading-relaxed line-clamp-2 mb-4 flex-1">{{ item.description }}</p>

              <div class="mt-auto pt-4 border-t border-white/[0.04] flex items-center justify-between">
                <span class="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a] flex items-center gap-1.5">
                  <span class="w-1.5 h-1.5 rounded-full" :class="CATEGORY_DOTS[item.category || 'productivity']"></span>
                  {{ CATEGORY_LABELS[item.category || 'productivity'] }}
                </span>
                <span class="text-[9px] font-semibold tracking-wider text-white bg-white/5 border border-white/10 px-2 py-0.5 rounded-md uppercase">
                  {{ SOURCE_TYPE_CONFIG[item.source_type]?.label || item.source_type }}
                </span>
              </div>

              <button
                @click.stop="configure(item)"
                class="mt-4 w-full py-2.5 text-[11px] font-bold uppercase tracking-wider rounded-xl transition-all duration-200 flex items-center justify-center gap-2"
                :class="instanceCountBySlug[item.slug]
                  ? 'bg-white/[0.04] hover:bg-white/[0.08] text-[#ececec] border border-white/10 hover:border-white/20'
                  : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-600/10 hover:shadow-blue-500/25 active:scale-[0.98]'
                "
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14"/><path d="M12 5v14"/>
                </svg>
                {{ instanceCountBySlug[item.slug] ? 'Nueva instancia' : 'Configurar' }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ── SECTION: MCP CUSTOM ── -->
      <section v-if="customItems.length > 0" class="space-y-4 animate-in">
        <div class="flex items-center gap-3">
          <div class="w-1.5 h-1.5 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]"></div>
          <h3 class="text-[11px] font-extrabold text-[#7a7a7a] uppercase tracking-widest">MCP Custom</h3>
          <span class="text-[10px] text-[#4a4a4a] font-semibold">{{ customItems.length }} disponible{{ customItems.length > 1 ? 's' : '' }}</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div
            v-for="item in customItems"
            :key="item.slug"
            @click="configure(item)"
            :style="`--glow-color: ${CATEGORY_RGBS[item.category || 'productivity'] || '251, 191, 36'}`"
            class="integration-card group relative bg-gradient-to-b from-white/[0.04] to-white/[0.01] border border-white/[0.06] rounded-2xl p-5 hover:border-white/15 hover:bg-white/[0.03] transition-all duration-300 hover:-translate-y-1.5 cursor-pointer overflow-hidden backdrop-blur-md"
          >
            <div class="absolute -right-4 -top-4 w-24 h-24 bg-white/[0.02] rounded-full blur-3xl group-hover:bg-white/[0.04] transition-all duration-500"></div>

            <div v-if="instanceCountBySlug[item.slug]" class="absolute top-4 right-4 flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
              <span class="relative flex h-1.5 w-1.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
              </span>
              <span class="text-emerald-400 text-[9px] font-bold uppercase tracking-wider">
                {{ instanceCountBySlug[item.slug] }} activa{{ (instanceCountBySlug[item.slug] || 0) > 1 ? 's' : '' }}
              </span>
            </div>

            <div class="flex flex-col h-full">
              <div class="w-11 h-11 rounded-xl flex items-center justify-center border transition-transform duration-500 group-hover:scale-110 mb-4"
                :class="CATEGORY_COLORS[item.category || 'productivity']"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path :d="CATEGORY_ICONS[item.category || 'productivity']"/>
                </svg>
              </div>

              <h3 class="text-sm font-semibold text-white mb-1.5 transition-colors">{{ item.name }}</h3>
              <p class="text-[12px] text-[#7a7a7a] leading-relaxed line-clamp-2 mb-4 flex-1">{{ item.description }}</p>

              <div class="mt-auto pt-4 border-t border-white/[0.04] flex items-center justify-between">
                <span class="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a] flex items-center gap-1.5">
                  <span class="w-1.5 h-1.5 rounded-full" :class="CATEGORY_DOTS[item.category || 'productivity']"></span>
                  {{ CATEGORY_LABELS[item.category || 'productivity'] }}
                </span>
                <span class="text-[9px] font-semibold tracking-wider text-white bg-white/5 border border-white/10 px-2 py-0.5 rounded-md uppercase">
                  {{ SOURCE_TYPE_CONFIG[item.source_type]?.label || item.source_type }}
                </span>
              </div>

              <button
                @click.stop="configure(item)"
                class="mt-4 w-full py-2.5 text-[11px] font-bold uppercase tracking-wider rounded-xl transition-all duration-200 flex items-center justify-center gap-2"
                :class="instanceCountBySlug[item.slug]
                  ? 'bg-white/[0.04] hover:bg-white/[0.08] text-[#ececec] border border-white/10 hover:border-white/20'
                  : 'bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white shadow-lg shadow-amber-600/10 hover:shadow-amber-500/25 active:scale-[0.98]'
                "
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14"/><path d="M12 5v14"/>
                </svg>
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
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.1);
}

.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.integration-card {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1),
              box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1),
              background-color 0.3s ease,
              border-color 0.3s ease;
}

.integration-card:hover {
  box-shadow: 0 10px 30px -10px rgba(var(--glow-color), 0.15),
              0 1px 1px 0 rgba(var(--glow-color), 0.05) inset;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-in {
  animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
