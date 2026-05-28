<script setup lang="ts">
import { ref, watch, computed } from 'vue'

export interface MCPSource {
  id: string;
  name: string;
  description?: string;
  type?: string;
}

export interface ToolConfig {
  name: string;
  description?: string;
  parameter_schema?: any;
  source_id?: string;
}

const props = defineProps<{
  sources: MCPSource[];
  tools: ToolConfig[];
  query: string;
  cursorPosition: number;
}>()

const emit = defineEmits<{
  (e: 'insert', newQuery: string, newCursorPos: number): void
  (e: 'close'): void
}>()

const isOpen = ref(false)
const searchTerm = ref('')
const currentStep = ref<'source' | 'tool' | 'property' | 'category' | 'field'>('source')
const selectedSource = ref<MCPSource | null>(null)
const selectedTool = ref<ToolConfig | null>(null)

// Constants for available properties based on our schema definitions
const PROPERTIES = [
  { id: 'params', label: 'Estructura JSON (params)', desc: 'Parámetros obligatorios u opcionales del endpoint' },
  { id: 'key_figures', label: 'Métricas Numéricas (key_figures)', desc: 'Campos numéricos filtrables con umbrales (min/max)' },
  { id: 'key_values', label: 'Valores Categóricos (key_values)', desc: 'Filtros exactos por texto o categoría' }
]

const startIdx = ref(-1)

watch([() => props.query, () => props.cursorPosition], ([newQuery, newPos]) => {
  if (newPos === 0 || !newQuery) {
    close()
    return
  }

  // Look backwards from cursor to find {{
  const textBeforeCursor = newQuery.slice(0, newPos)
  const match = textBeforeCursor.match(/\{\{([a-zA-Z0-9_.-]*)$/)

  if (match) {
    isOpen.value = true
    searchTerm.value = match[1].toLowerCase()
    startIdx.value = newPos - match[1].length - 2 // Index of first '{'
    
    // Determine step based on dots
    if (searchTerm.value.includes('.')) {
      const parts = searchTerm.value.split('.')
      const sourceName = parts[0]
      const toolName = parts[1]
      
      if (parts.length === 2) {
        // e.g. "maquinaria." -> Looking for tool
        currentStep.value = 'tool'
        selectedSource.value = props.sources.find(s => s.name.toLowerCase() === sourceName) || null
        selectedTool.value = null
      } else if (parts.length === 3) {
        // e.g. "maquinaria.get_maquinaria." -> Looking for property
        currentStep.value = 'property'
        selectedSource.value = props.sources.find(s => s.name.toLowerCase() === sourceName) || null
        selectedTool.value = props.tools.find(t => t.name.toLowerCase() === toolName) || null
      } else if (parts.length === 4) {
        // e.g. "maquinaria.get_maquinaria.key_values." -> Looking for category OR field
        const propName = parts[2]
        selectedSource.value = props.sources.find(s => s.name.toLowerCase() === sourceName) || null
        selectedTool.value = props.tools.find(t => t.name.toLowerCase() === toolName) || null
        if (propName === 'key_values') {
          currentStep.value = 'category'
        } else {
          currentStep.value = 'field'
        }
      } else {
        // e.g. "maquinaria.get_maquinaria.key_values.Status." -> Looking for field
        currentStep.value = 'field'
        selectedSource.value = props.sources.find(s => s.name.toLowerCase() === sourceName) || null
        selectedTool.value = props.tools.find(t => t.name.toLowerCase() === toolName) || null
      }
    } else {
      currentStep.value = 'source'
      selectedSource.value = null
      selectedTool.value = null
    }
  } else {
    close()
  }
})

function close() {
  isOpen.value = false
  searchTerm.value = ''
  currentStep.value = 'source'
  selectedSource.value = null
  selectedTool.value = null
  startIdx.value = -1
  emit('close')
}

const filteredOptions = computed(() => {
  if (currentStep.value === 'source') {
    return props.sources.filter(s => s.name.toLowerCase().includes(searchTerm.value))
  } else if (currentStep.value === 'tool') {
    const parentSourceId = selectedSource.value?.id
    const toolSearch = searchTerm.value.split('.')[1] || ''
    return props.tools.filter(t => 
      t.source_id === parentSourceId && 
      t.name.toLowerCase().includes(toolSearch)
    )
  } else if (currentStep.value === 'property' && selectedTool.value) {
    const propertySearch = searchTerm.value.split('.')[2] || ''
    return PROPERTIES.filter(p => p.id.includes(propertySearch) || p.label.toLowerCase().includes(propertySearch))
  } else if (currentStep.value === 'category' && selectedTool.value) {
    const propertySearch = searchTerm.value.split('.')[2] // 'key_values'
    const categorySearch = searchTerm.value.split('.')[3]?.toLowerCase() || ''
    
    let categories: {id: string, label: string}[] = []
    const schema = selectedTool.value.parameter_schema || {}
    const filterable = schema.filterable_schema || {}
    
    if (propertySearch === 'key_values') {
      const kv = filterable.key_values || {}
      categories = Object.keys(kv).map(k => ({ id: k, label: `${k} (Columna)` }))
    }
    
    return categories.filter(c => c.label.toLowerCase().includes(categorySearch))

  } else if (currentStep.value === 'field' && selectedTool.value) {
    const propertySearch = searchTerm.value.split('.')[2] // 'params', 'key_figures', etc.
    let fieldSearch = ''
    
    let fields: {id: string, label: string}[] = []
    const schema = selectedTool.value.parameter_schema || {}
    const filterable = schema.filterable_schema || {}
    
    if (propertySearch === 'params') {
      fieldSearch = searchTerm.value.split('.')[3]?.toLowerCase() || ''
      const props = schema.properties || {}
      fields = Object.keys(props).map(k => ({ id: k, label: k }))
    } else if (propertySearch === 'key_figures') {
      fieldSearch = searchTerm.value.split('.')[3]?.toLowerCase() || ''
      const kf = filterable.key_figures || []
      fields = kf.map((k: string) => ({ id: k, label: k }))
    } else if (propertySearch === 'key_values') {
      const categoryNameLower = searchTerm.value.split('.')[3]
      fieldSearch = searchTerm.value.split('.')[4]?.toLowerCase() || ''
      const kv = filterable.key_values || {}
      
      const actualCategoryKey = Object.keys(kv).find(k => k.toLowerCase() === categoryNameLower)
      const vals = actualCategoryKey ? kv[actualCategoryKey] : []
      if (Array.isArray(vals)) {
        fields = vals.map(v => ({ id: String(v), label: String(v) }))
      }
    }
    
    return fields.filter(f => f.label.toLowerCase().includes(fieldSearch))
  }
  return []
})

function selectOption(option: any) {
  if (currentStep.value === 'source') {
    const sourceName = option.name;
    const replacement = `{{${sourceName}.`
    const newQuery = props.query.substring(0, startIdx.value) + replacement + props.query.substring(props.cursorPosition)
    emit('insert', newQuery, startIdx.value + replacement.length)
  } else if (currentStep.value === 'tool') {
    const sourceName = selectedSource.value?.name;
    const toolName = option.name;
    const replacement = `{{${sourceName}.${toolName}.`
    const newQuery = props.query.substring(0, startIdx.value) + replacement + props.query.substring(props.cursorPosition)
    emit('insert', newQuery, startIdx.value + replacement.length)
  } else if (currentStep.value === 'property') {
    // Insert property AND a dot to see fields
    const sourceName = selectedSource.value?.name
    const toolName = selectedTool.value?.name
    const propertyName = option.id
    const replacement = `{{${sourceName}.${toolName}.${propertyName}.`
    const newQuery = props.query.substring(0, startIdx.value) + replacement + props.query.substring(props.cursorPosition)
    emit('insert', newQuery, startIdx.value + replacement.length)
  } else if (currentStep.value === 'category') {
    // Insert category AND a dot to see values
    const parts = searchTerm.value.split('.')
    const sourceName = parts[0]
    const toolName = parts[1]
    const propertyName = parts[2]
    const categoryName = option.id
    const replacement = `{{${sourceName}.${toolName}.${propertyName}.${categoryName}.`
    const newQuery = props.query.substring(0, startIdx.value) + replacement + props.query.substring(props.cursorPosition)
    emit('insert', newQuery, startIdx.value + replacement.length)
  } else if (currentStep.value === 'field') {
    // Insert field AND closing braces
    const parts = searchTerm.value.split('.')
    const sourceName = parts[0]
    const toolName = parts[1]
    const propertyName = parts[2]
    
    let replacement = ''
    if (propertyName === 'key_values') {
      const categoryName = parts[3]
      const fieldName = option.id
      replacement = `{{${sourceName}.${toolName}.${propertyName}.${categoryName}.${fieldName}}}`
    } else {
      const fieldName = option.id
      replacement = `{{${sourceName}.${toolName}.${propertyName}.${fieldName}}}`
    }
    const newQuery = props.query.substring(0, startIdx.value) + replacement + props.query.substring(props.cursorPosition)
    emit('insert', newQuery, startIdx.value + replacement.length)
    close()
  }
}
</script>

<template>
  <div v-if="isOpen" class="absolute z-50 bg-[#2f2f2f] border border-white/10 rounded-xl shadow-2xl py-2 w-80 max-h-64 overflow-y-auto custom-scrollbar animate-in" style="bottom: 100%; left: 0; margin-bottom: 8px;">
    
    <!-- HEADER -->
    <div class="px-3 pb-2 mb-1 border-b border-white/5 flex items-center justify-between">
      <span class="text-[11px] font-bold text-[#7a7a7a] uppercase tracking-wider">
        {{ currentStep === 'source' ? 'Seleccionar Fuente (MCP)' : currentStep === 'tool' ? `Fuente: ${selectedSource?.name}` : currentStep === 'property' ? `Herramienta: ${selectedTool?.name}` : currentStep === 'category' ? 'Seleccionar Columna' : 'Seleccionar Valor' }}
      </span>
      <button @click="close" class="text-[#7a7a7a] hover:text-white p-0.5 rounded-full hover:bg-white/5">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
      </button>
    </div>

    <!-- LIST -->
    <div class="px-1 space-y-0.5">
      <div v-if="filteredOptions.length === 0" class="px-3 py-4 text-center text-[13px] text-[#7a7a7a]">
        No hay coincidencias.
      </div>

      <template v-else-if="currentStep === 'source'">
        <button 
          v-for="source in filteredOptions" :key="source.id"
          @click.prevent="selectOption(source)"
          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex flex-col gap-0.5 hover:bg-white/5 group"
        >
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-amber-400 shrink-0"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m8 17 4 4 4-4"/></svg>
            <span class="font-medium text-[#ececec] truncate">{{ source.name }}</span>
            <span class="text-[10px] text-[#7a7a7a] bg-black/20 px-1.5 py-0.5 rounded border border-white/5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Seleccionar</span>
          </div>
          <span class="text-[11px] text-[#7a7a7a] line-clamp-1 ml-5">{{ source.type }} - {{ source.url }}</span>
        </button>
      </template>
      
      <template v-else-if="currentStep === 'tool'">
        <button 
          v-for="tool in filteredOptions" :key="tool.name"
          @click.prevent="selectOption(tool)"
          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex flex-col gap-0.5 hover:bg-white/5 group"
        >
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-indigo-400 shrink-0"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" x2="12" y1="22" y2="12"/></svg>
            <span class="font-medium text-[#ececec] truncate">{{ tool.name }}</span>
            <span class="text-[10px] text-[#7a7a7a] bg-black/20 px-1.5 py-0.5 rounded border border-white/5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Seleccionar</span>
          </div>
          <span v-if="tool.description" class="text-[11px] text-[#7a7a7a] line-clamp-1 ml-5">{{ tool.description }}</span>
        </button>
      </template>

      <template v-else-if="currentStep === 'property'">
        <button 
          v-for="prop in filteredOptions" :key="prop.id"
          @click.prevent="selectOption(prop)"
          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex flex-col gap-0.5 hover:bg-white/5 group"
        >
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400 shrink-0"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/></svg>
            <span class="font-medium text-[#ececec] truncate">{{ prop.label }}</span>
            <span class="text-[10px] text-[#7a7a7a] bg-black/20 px-1.5 py-0.5 rounded border border-white/5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Ver Campos</span>
          </div>
          <span class="text-[11px] text-[#7a7a7a] line-clamp-1 ml-5">{{ prop.desc }}</span>
        </button>
      </template>

      <template v-else-if="currentStep === 'category'">
        <button 
          v-for="cat in filteredOptions" :key="cat.id"
          @click.prevent="selectOption(cat)"
          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex flex-col gap-0.5 hover:bg-white/5 group"
        >
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-pink-400 shrink-0"><path d="M4 9h16"/><path d="M4 15h16"/><path d="M10 3L8 21"/><path d="M16 3l-2 18"/></svg>
            <span class="font-medium text-[#ececec] truncate">{{ cat.label }}</span>
            <span class="text-[10px] text-[#7a7a7a] bg-black/20 px-1.5 py-0.5 rounded border border-white/5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Ver Valores</span>
          </div>
        </button>
      </template>

      <template v-else-if="currentStep === 'field'">
        <button 
          v-for="field in filteredOptions" :key="field.id"
          @click.prevent="selectOption(field)"
          class="w-full text-left px-3 py-2 text-[13px] rounded-lg transition-colors flex flex-col gap-0.5 hover:bg-white/5 group"
        >
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-cyan-400 shrink-0"><circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/></svg>
            <span class="font-medium text-[#ececec] truncate" :title="field.label">{{ field.label }}</span>
            <span class="text-[10px] text-[#7a7a7a] bg-black/20 px-1.5 py-0.5 rounded border border-white/5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Insertar</span>
          </div>
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-in {
  animation: fadeIn 0.2s ease-out forwards;
}
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
