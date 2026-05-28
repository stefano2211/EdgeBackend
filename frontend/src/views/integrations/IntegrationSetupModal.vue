<script setup lang="ts">
import { ref, computed } from 'vue'
import integrationService, { type IntegrationCatalog } from '@/services/integrationService'
import GmailOAuthModal from './GmailOAuthModal.vue'

const props = defineProps<{
  catalog: IntegrationCatalog
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'created'): void
}>()

const step = ref(1)
const instanceName = ref('')
const availableInChat = ref(true)
const availableInReactive = ref(true)
const credentials = ref<Record<string, string>>({})
const isSubmitting = ref(false)
const instanceId = ref<number | null>(null)
const oauthError = ref('')

const requiredFields = computed(() => {
  return props.catalog.auth_env_var_mapping ? Object.keys(props.catalog.auth_env_var_mapping) : []
})

function reset() {
  step.value = 1
  instanceName.value = ''
  availableInChat.value = true
    availableInReactive.value = true
  credentials.value = {}
  isSubmitting.value = false
  instanceId.value = null
}

function close() {
  reset()
  emit('close')
}

async function createInstance() {
  isSubmitting.value = true
  try {
    const instance = await integrationService.createInstance({
      catalog_slug: props.catalog.slug,
      instance_name: instanceName.value || `${props.catalog.name}`,
      available_in_chat: availableInChat.value,
      available_in_reactive: availableInReactive.value,
    })
    instanceId.value = instance.id
    step.value = 2
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Error al crear instancia')
  } finally {
    isSubmitting.value = false
  }
}

    async function submitCredentials() {
        if (!instanceId.value) return
        isSubmitting.value = true
        try {
            // Map env-var keys (e.g. GMAIL_REFRESH_TOKEN) → semantic keys (e.g. refresh_token)
            // as expected by the backend auth strategies.
            const mapped: Record<string, string> = {}
            if (props.catalog.auth_env_var_mapping) {
                for (const [envVar, credKey] of Object.entries(props.catalog.auth_env_var_mapping)) {
                    mapped[credKey] = credentials.value[envVar] || ''
                }
            }
            await integrationService.submitCredentials(instanceId.value, mapped)
            step.value = 3
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Error al enviar credenciales')
        } finally {
            isSubmitting.value = false
        }
    }

    function onOAuthSuccess() {
        step.value = 3
    }

    function onOAuthError(message: string) {
        oauthError.value = message
    }

async function finish() {
  emit('created')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[9999] flex items-center justify-center p-4">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="close"></div>

        <!-- Modal -->
        <div class="relative bg-[#1c1c1c] rounded-3xl shadow-2xl border border-white/[0.08] w-full max-w-lg overflow-hidden">
          <!-- Header -->
          <div class="px-6 py-5 border-b border-white/[0.06] flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center text-violet-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
              </div>
              <div>
                <h3 class="text-white font-semibold">Configurar {{ catalog.name }}</h3>
                <p class="text-[#7a7a7a] text-[12px]">Paso {{ step }} de 3</p>
              </div>
            </div>
            <button @click="close" class="text-[#7a7a7a] hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>

          <!-- Step 1: Setup Guide + Instance Config -->
          <div v-if="step === 1" class="p-6 space-y-6">
            <div class="bg-[#2f2f2f]/30 border border-white/[0.06] rounded-2xl p-4 max-h-40 overflow-y-auto custom-scrollbar">
              <div class="prose prose-invert prose-sm max-w-none text-[#b4b4b4]" v-html="catalog.auth_setup_guide_markdown"></div>
            </div>

            <div class="space-y-4">
              <div class="space-y-1.5">
                <label class="text-[12px] font-bold text-[#7a7a7a] uppercase ml-1">Nombre de instancia</label>
                <input
                  v-model="instanceName"
                  type="text"
                  :placeholder="`Mi ${catalog.name}`"
                  class="w-full bg-[#1a1a1a] border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-violet-500/50 outline-none"
                >
              </div>

              <div class="flex items-center gap-6">
                <div class="flex items-center gap-3">
                  <span class="text-[12px] text-[#7a7a7a]">Chat</span>
                  <div
                    @click="availableInChat = !availableInChat"
                    class="relative w-10 h-5 rounded-full transition-all cursor-pointer border shrink-0"
                    :class="availableInChat ? 'bg-violet-500/20 border-violet-500/40' : 'bg-white/5 border-white/10'"
                  >
                    <div class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all"
                      :class="availableInChat ? 'left-6 bg-violet-400 shadow-[0_0_8px_rgba(139,92,246,0.5)]' : 'left-1 bg-[#4a4a4a]'"
                    ></div>
                  </div>
                </div>
                <div class="flex items-center gap-3">
                  <span class="text-[12px] text-[#7a7a7a]">Eventos</span>
                  <div
                    @click="availableInReactive = !availableInReactive"
                    class="relative w-10 h-5 rounded-full transition-all cursor-pointer border shrink-0"
                    :class="availableInReactive ? 'bg-emerald-500/20 border-emerald-500/40' : 'bg-white/5 border-white/10'"
                  >
                    <div class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all"
                      :class="availableInReactive ? 'left-6 bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'left-1 bg-[#4a4a4a]'"
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            <button
              @click="createInstance"
              :disabled="isSubmitting"
              class="w-full py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-medium rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-600/20"
            >
              <svg v-if="isSubmitting" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              <span>{{ isSubmitting ? 'Creando...' : 'Continuar' }}</span>
            </button>
          </div>

          <!-- Step 2: Credentials -->
          <div v-if="step === 2" class="p-6 space-y-6">
            <!-- OAuth2 flow (e.g. Gmail) -->
            <GmailOAuthModal
              v-if="catalog.auth_type === 'oauth2'"
              :instance-id="instanceId!"
              @success="step = 3"
              @error="oauthError = $event"
            />

            <!-- Manual credentials for token / basic / api_key -->
            <template v-else>
              <p class="text-[13px] text-[#7a7a7a]">
                Introduce las credenciales requeridas para <span class="text-white font-medium">{{ catalog.name }}</span>:
              </p>

              <div class="space-y-4">
                <div
                  v-for="(envVar, credKey) in catalog.auth_env_var_mapping"
                  :key="credKey"
                  class="space-y-1.5"
                >
                  <label class="text-[12px] font-bold text-[#7a7a7a] uppercase ml-1">{{ credKey }}</label>
                  <input
                    v-model="credentials[credKey]"
                    :type="credKey.toLowerCase().includes('secret') || credKey.toLowerCase().includes('token') ? 'password' : 'text'"
                    :placeholder="`Valor para ${credKey}`"
                    class="w-full bg-[#1a1a1a] border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-violet-500/50 outline-none"
                  >
                </div>

                <button
                  @click="submitCredentials"
                  :disabled="isSubmitting || requiredFields.some(f => !credentials[f])"
                  class="w-full py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-medium rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-600/20"
                >
                  <svg v-if="isSubmitting" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  <span>{{ isSubmitting ? 'Enviando...' : 'Enviar credenciales' }}</span>
                </button>
              </div>
            </template>

            <!-- OAuth error display -->
            <div v-if="oauthError" class="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-red-400 text-[12px]">
              {{ oauthError }}
            </div>
          </div>

          <!-- Step 3: Success -->
          <div v-if="step === 3" class="p-6 text-center space-y-6">
            <div class="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto text-emerald-400">
              <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            </div>
            <div>
              <h3 class="text-white font-semibold text-lg">¡Instancia creada!</h3>
              <p class="text-[#7a7a7a] text-sm mt-1">{{ instanceName }} está configurada y lista para usar.</p>
            </div>
            <button
              @click="finish"
              class="w-full py-3 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-xl transition-all shadow-lg shadow-violet-600/20"
            >
              Finalizar y sincronizar tools
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active { transition: all 0.15s ease-in; }
.modal-enter-from, .modal-leave-to { opacity: 0; transform: scale(0.95); }

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 10px; }
</style>
