<script setup lang="ts">
import { ref, onMounted } from 'vue'
import promptService, { type Prompt } from '@/services/promptService'

interface ChatParams {
  system_prompt: string
  temperature: number | null
  max_tokens: number | null
  top_p: number | null
  top_k: number | null
  seed: number | null
  stop_sequence: string
}

const props = defineProps<{
  isOpen: boolean
  params: ChatParams
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const savedPrompts = ref<Prompt[]>([])
const isLoading = ref(false)
const selectedPromptId = ref<string>('')
const presetName = ref('')
const isSaving = ref(false)

onMounted(async () => {
  await fetchPrompts()
})

async function fetchPrompts() {
  try {
    isLoading.value = true
    savedPrompts.value = await promptService.listPrompts()
    // Find active or first if none active? 
    // For now just load the list
  } catch (error) {
    console.error('Error fetching prompts:', error)
  } finally {
    isLoading.value = false
  }
}

function applyPreset(promptId: string) {
  const prompt = savedPrompts.value.find(p => p.id === promptId)
  if (!prompt) return

  props.params.system_prompt = prompt.system_prompt || ''
  props.params.temperature = prompt.temperature ?? null
  props.params.max_tokens = prompt.max_tokens ?? null
  props.params.top_p = prompt.top_p ?? null
  props.params.top_k = prompt.top_k ?? null
  props.params.seed = prompt.seed ?? null
  props.params.stop_sequence = prompt.stop_sequence || ''
  
  selectedPromptId.value = promptId
}

async function saveAsPreset() {
  if (!presetName.value.trim()) return
  
  try {
    isSaving.value = true
    const newPreset = await promptService.createPrompt({
      title: presetName.value,
      system_prompt: props.params.system_prompt,
      temperature: props.params.temperature,
      max_tokens: props.params.max_tokens,
      top_p: props.params.top_p,
      top_k: props.params.top_k,
      seed: props.params.seed,
      stop_sequence: props.params.stop_sequence
    })
    
    savedPrompts.value.push(newPreset)
    selectedPromptId.value = newPreset.id
    presetName.value = ''
  } catch (error) {
    console.error('Error saving preset:', error)
  } finally {
    isSaving.value = false
  }
}

function resetAll() {
  props.params.system_prompt = ''
  props.params.temperature = null
  props.params.max_tokens = null
  props.params.top_p = null
  props.params.top_k = null
  props.params.seed = null
  props.params.stop_sequence = ''
  selectedPromptId.value = ''
}

function formatValue(val: number | null): string {
  return val === null ? 'Default' : String(val)
}

function onPresetChange(e: Event) {
  const target = e.target as HTMLSelectElement
  applyPreset(target.value)
}

function onTemperatureInput(e: Event) {
  const target = e.target as HTMLInputElement
  props.params.temperature = parseFloat(target.value)
}

function onMaxTokensInput(e: Event) {
  const target = e.target as HTMLInputElement
  props.params.max_tokens = target.value ? parseInt(target.value) : null
}

function onTopPInput(e: Event) {
  const target = e.target as HTMLInputElement
  props.params.top_p = parseFloat(target.value)
}

function onTopKInput(e: Event) {
  const target = e.target as HTMLInputElement
  props.params.top_k = target.value ? parseInt(target.value) : null
}

function onSeedInput(e: Event) {
  const target = e.target as HTMLInputElement
  props.params.seed = target.value ? parseInt(target.value) : null
}
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition name="fade">
      <div v-if="isOpen" class="fixed inset-0 bg-black/40 z-40" @click="emit('close')"></div>
    </Transition>

    <!-- Drawer -->
    <Transition name="slide">
      <div v-if="isOpen" class="fixed top-0 right-0 h-full w-[380px] max-w-full bg-[#171717] border-l border-white/[0.06] z-50 flex flex-col shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div class="flex items-center gap-2">
            <span class="px-3 py-1 bg-white/10 text-white text-[13px] font-medium rounded-lg">Controls</span>
            <span class="text-[13px] text-[#7a7a7a] cursor-pointer hover:text-white px-2 py-1 rounded-lg hover:bg-white/5 transition-colors">Overview</span>
          </div>
          <button @click="emit('close')" class="p-1.5 text-[#7a7a7a] hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>

        <!-- Scrollable Content -->
        <div class="flex-1 overflow-y-auto px-5 py-4 space-y-5">

          <!-- Presets -->
          <div class="space-y-2">
            <h3 class="text-[14px] font-semibold text-white">Presets</h3>
            <div class="flex gap-2">
              <select 
                v-model="selectedPromptId"
                @change="onPresetChange"
                class="flex-1 bg-[#212121] border border-white/[0.08] rounded-xl px-3 py-2 text-[13px] text-white focus:outline-none focus:border-white/20 transition-colors"
              >
                <option value="">Manual Configuration</option>
                <option v-for="prompt in savedPrompts" :key="prompt.id" :value="prompt.id">
                  {{ prompt.title }}
                </option>
              </select>
              <button 
                @click="fetchPrompts"
                class="p-2 text-[#7a7a7a] hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                title="Refresh presets"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
              </button>
            </div>
            
            <div class="flex gap-2 pt-1">
              <input 
                v-model="presetName"
                placeholder="New preset name"
                class="flex-1 bg-transparent border border-white/[0.08] rounded-lg px-2 py-1 text-[12px] text-white placeholder-[#5a5a5a] focus:outline-none focus:border-white/20"
                @keyup.enter="saveAsPreset"
              />
              <button 
                @click="saveAsPreset"
                :disabled="!presetName.trim() || isSaving"
                class="px-2 py-1 bg-white/10 hover:bg-white/20 disabled:opacity-50 text-white text-[11px] font-medium rounded-lg transition-colors"
              >
                {{ isSaving ? 'Saving...' : 'Save Current' }}
              </button>
            </div>
          </div>

          <div class="border-t border-white/[0.06]"></div>

          <!-- System Prompt -->
          <div class="space-y-2">
            <h3 class="text-[14px] font-semibold text-white">System Prompt</h3>
            <textarea 
              v-model="params.system_prompt"
              placeholder="Enter system prompt"
              rows="3"
              class="w-full bg-[#212121] border border-white/[0.08] rounded-xl px-4 py-3 text-[13px] text-white placeholder-[#7a7a7a] resize-none focus:outline-none focus:border-white/20 transition-colors"
            ></textarea>
          </div>

          <div class="border-t border-white/[0.06]"></div>

          <!-- Advanced Params -->
          <div>
            <h3 class="text-[14px] font-semibold text-white mb-4">Advanced Params</h3>
            <div class="space-y-4">
              
              <!-- Temperature -->
              <div class="flex items-center justify-between">
                <label class="text-[13px] text-[#b4b4b4]">Temperature</label>
                <div class="flex items-center gap-2">
                  <input 
                    type="range" 
                    min="0" max="2" step="0.1"
                    :value="params.temperature ?? 0"
                    @input="onTemperatureInput"
                    class="range-input"
                  />
                  <button 
                    @click="params.temperature = null"
                    class="text-[12px] font-medium min-w-[55px] text-right"
                    :class="params.temperature === null ? 'text-[#7a7a7a]' : 'text-white'"
                  >
                    {{ formatValue(params.temperature) }}
                  </button>
                </div>
              </div>

              <!-- Max Tokens -->
              <div class="flex items-center justify-between">
                <label class="text-[13px] text-[#b4b4b4]">max_tokens</label>
                <input 
                  type="number" 
                  min="1" max="128000"
                  :value="params.max_tokens ?? ''"
                  @input="onMaxTokensInput"
                  placeholder="Default"
                  class="number-input"
                />
              </div>

              <!-- Top P -->
              <div class="flex items-center justify-between">
                <label class="text-[13px] text-[#b4b4b4]">top_p</label>
                <div class="flex items-center gap-2">
                  <input 
                    type="range" 
                    min="0" max="1" step="0.05"
                    :value="params.top_p ?? 1"
                    @input="onTopPInput"
                    class="range-input"
                  />
                  <button 
                    @click="params.top_p = null"
                    class="text-[12px] font-medium min-w-[55px] text-right"
                    :class="params.top_p === null ? 'text-[#7a7a7a]' : 'text-white'"
                  >
                    {{ formatValue(params.top_p) }}
                  </button>
                </div>
              </div>

              <!-- Top K -->
              <div class="flex items-center justify-between">
                <label class="text-[13px] text-[#b4b4b4]">top_k</label>
                <input 
                  type="number" 
                  min="1" max="100"
                  :value="params.top_k ?? ''"
                  @input="onTopKInput"
                  placeholder="Default"
                  class="number-input"
                />
              </div>

              <!-- Seed -->
              <div class="flex items-center justify-between">
                <label class="text-[13px] text-[#b4b4b4]">Seed</label>
                <input 
                  type="number" 
                  min="0"
                  :value="params.seed ?? ''"
                  @input="onSeedInput"
                  placeholder="Default"
                  class="number-input"
                />
              </div>

              <!-- Stop Sequence -->
              <div class="flex items-center justify-between">
                <label class="text-[13px] text-[#b4b4b4]">Stop Sequence</label>
                <input 
                  type="text"
                  v-model="params.stop_sequence"
                  placeholder="Default"
                  class="number-input"
                />
              </div>

            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-5 py-3 border-t border-white/[0.06]">
          <button 
            @click="resetAll"
            class="w-full text-[13px] font-medium text-[#7a7a7a] hover:text-white py-2 hover:bg-white/5 rounded-xl transition-colors"
          >
            Reset to Defaults
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.slide-enter-active { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-leave-active { transition: transform 0.2s ease-in; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }

.range-input {
  width: 6rem;
  height: 0.25rem;
  accent-color: white;
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 9999px;
  appearance: none;
  cursor: pointer;
}
.range-input::-webkit-slider-thumb {
  appearance: none;
  width: 0.75rem;
  height: 0.75rem;
  background-color: white;
  border-radius: 9999px;
}

.number-input {
  width: 6rem;
  background-color: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.5rem;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-size: 12px;
  text-align: right;
  color: white;
  outline: none;
  transition: border-color 0.2s;
}
.number-input:focus {
  border-color: rgba(255, 255, 255, 0.2);
}
.number-input::placeholder {
  color: #7a7a7a;
}
</style>
