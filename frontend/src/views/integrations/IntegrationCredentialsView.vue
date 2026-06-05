<script setup lang="ts">
import { ref, onMounted } from 'vue'
import integrationService, { type IntegrationInstance } from '@/services/integrationService'
import { reactiveCredentialService, type ReactiveCredential } from '@/services/reactiveCredentialService'

const integrationInstances = ref<IntegrationInstance[]>([])
const reactiveCredentials = ref<ReactiveCredential[]>([])
const isLoading = ref(true)

// Create Modal state
const showCreateModal = ref(false)
const isCreating = ref(false)
const deletingId = ref<number | null>(null)

const form = ref({
  name: '',
  key_identifier: '',
  fields: [{ key: '', value: '', isSecret: true }],
  description: '',
})

function addField() {
  form.value.fields.push({ key: '', value: '', isSecret: true })
}

function removeField(index: number) {
  if (form.value.fields.length > 1) {
    form.value.fields.splice(index, 1)
  }
}

function openCreate() {
  form.value = { name: '', key_identifier: '', fields: [{ key: '', value: '', isSecret: true }], description: '' }
  showCreateModal.value = true
}

async function loadData() {
  isLoading.value = true
  try {
    const [instRes, credRes] = await Promise.all([
      integrationService.listInstances(),
      reactiveCredentialService.list(),
    ])
    integrationInstances.value = instRes
    reactiveCredentials.value = credRes
  } catch (e) {
    console.error('Failed to load credentials', e)
  } finally {
    isLoading.value = false
  }
}

async function rotateIntegrationCredentials(instanceId: number) {
  if (!confirm('¿Rotar credenciales? Se eliminarán las actuales y deberás configurar de nuevo.')) return
  try {
    await integrationService.deleteInstance(instanceId)
    await loadData()
  } catch (e) {
    console.error('Failed to rotate', e)
  }
}

async function deleteReactiveCredential(id: number) {
  if (!confirm('¿Eliminar esta credencial permanentemente? El valor encriptado será destruido.')) return
  deletingId.value = id
  try {
    await reactiveCredentialService.remove(id)
    await loadData()
  } catch (e) {
    console.error('Failed to delete credential', e)
  } finally {
    deletingId.value = null
  }
}

async function createCredential() {
  const validFields = form.value.fields.filter(f => f.key.trim() && f.value.trim())
  if (!form.value.name.trim() || !form.value.key_identifier.trim() || validFields.length === 0) return
  
  isCreating.value = true
  try {
    const payload = Object.fromEntries(validFields.map(f => [f.key.trim(), f.value]))
    
    await reactiveCredentialService.create({
      name: form.value.name.trim(),
      key_identifier: form.value.key_identifier.trim().toUpperCase().replace(/\s+/g, '_'),
      value: JSON.stringify(payload),
      description: form.value.description.trim() || undefined,
    })
    showCreateModal.value = false
    form.value = { name: '', key_identifier: '', fields: [{ key: '', value: '', isSecret: true }], description: '' }
    await loadData()
  } catch (err: any) {
    if (err?.response?.status === 409) {
      alert('Ya existe una credencial con ese Key Identifier.')
    } else {
      console.error('Failed to create credential', err)
    }
  } finally {
    isCreating.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="px-6 py-6 max-w-6xl mx-auto space-y-8 h-full overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="relative overflow-hidden p-6 rounded-2xl border border-white/[0.04] bg-gradient-to-r from-white/[0.03] to-white/[0.01] backdrop-blur-md">
      <div class="absolute -left-12 -top-12 w-48 h-48 bg-amber-600/5 rounded-full blur-3xl"></div>
      <div class="absolute -right-12 -bottom-12 w-48 h-48 bg-violet-600/5 rounded-full blur-3xl"></div>
      
      <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 class="text-2xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-[#ececec] to-[#999999]">
            Centro de Credenciales
          </h2>
          <p class="text-[#7a7a7a] text-xs md:text-sm mt-1 max-w-xl">
            Gestiona de forma segura tus contraseñas y llaves de acceso encriptadas para integraciones MCP y flujos de automatización reactiva.
          </p>
        </div>
        <div class="flex items-center gap-3 self-start md:self-auto">
          <div class="flex flex-col items-end text-right">
            <span class="text-[11px] font-bold text-amber-500 uppercase tracking-widest">Encriptación AES-256</span>
            <span class="text-[10px] text-[#7a7a7a] mt-0.5">Almacenamiento ultra seguro</span>
          </div>
          <div class="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Security Notice Banner -->
    <div class="bg-amber-500/5 border border-amber-500/10 rounded-2xl p-4 flex items-start gap-3 backdrop-blur-md">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-400 shrink-0 mt-0.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      <div>
        <p class="text-[11px] font-bold text-amber-400 uppercase tracking-wider mb-0.5">Nota de Seguridad</p>
        <p class="text-[12px] text-[#7a7a7a] leading-relaxed">
          Las contraseñas y tokens se almacenan de manera encriptada usando Fernet. El texto plano nunca se envía al navegador. Solo los agentes pueden desencriptar los secretos para iniciar sesión de forma autónoma.
        </p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="py-20 text-center animate-pulse">
      <svg class="animate-spin w-8 h-8 text-amber-500 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="text-[#7a7a7a] text-sm">Cargando llaves y credenciales...</p>
    </div>

    <template v-else>
      <!-- Integrations MCP -->
      <section class="space-y-4 animate-in">
        <div class="flex items-center gap-3">
          <div class="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.5)]"></div>
          <h3 class="text-[11px] font-extrabold text-[#7a7a7a] uppercase tracking-widest">Integraciones (MCP)</h3>
          <span class="text-[10px] text-[#4a4a4a] font-semibold">{{ integrationInstances.length }} activas</span>
        </div>

        <div v-if="integrationInstances.length === 0" class="py-10 bg-white/[0.01] border border-dashed border-white/10 rounded-2xl text-center">
          <p class="text-[#4a4a4a] text-xs">No hay credenciales activas para servidores MCP.</p>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="inst in integrationInstances"
            :key="inst.id"
            class="bg-gradient-to-r from-white/[0.03] to-white/[0.01] border border-white/[0.06] rounded-2xl p-4 flex items-center justify-between group hover:border-white/10 transition-all duration-300"
          >
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400 group-hover:scale-105 transition-transform duration-300">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
              </div>
              <div>
                <h4 class="text-white font-semibold text-xs">{{ inst.instance_name }}</h4>
                <p class="text-[#7a7a7a] text-[11px] mt-0.5">{{ inst.catalog?.name }} • {{ inst.catalog?.auth_type }}</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <button
                @click="rotateIntegrationCredentials(inst.id)"
                class="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-400 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 hover:border-amber-500/30 rounded-lg transition-all duration-200 active:scale-[0.98]"
              >
                Rotar
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Separator -->
      <div class="border-t border-white/[0.04]"></div>

      <!-- Reactive Automation -->
      <section class="space-y-4 animate-in">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-1.5 h-1.5 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]"></div>
            <h3 class="text-[11px] font-extrabold text-[#7a7a7a] uppercase tracking-widest">Automatización (Browser/VL)</h3>
            <span class="text-[10px] text-[#4a4a4a] font-semibold">{{ reactiveCredentials.length }} guardadas</span>
          </div>
          
          <button
            @click="openCreate"
            class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold rounded-xl transition-all duration-200 shadow-lg shadow-amber-500/10 hover:shadow-amber-500/25 active:scale-[0.98] flex items-center gap-1.5 cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
            Nueva Credencial
          </button>
        </div>

        <div v-if="reactiveCredentials.length === 0" class="py-16 bg-white/[0.01] border border-dashed border-white/10 rounded-2xl text-center max-w-md mx-auto">
          <div class="w-10 h-10 rounded-xl bg-amber-500/5 border border-amber-500/10 flex items-center justify-center mx-auto mb-3 text-amber-500/40">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
          </div>
          <p class="text-[#ececec] text-xs font-semibold mb-1">Sin credenciales configuradas</p>
          <p class="text-[#7a7a7a] text-[11px] max-w-[280px] mx-auto mb-4">Añade contraseñas para que los agentes puedan iniciar sesión de forma autónoma.</p>
          <button
            @click="openCreate"
            class="px-4 py-2 bg-white text-black text-[11px] font-bold rounded-lg hover:bg-[#ececec] transition-colors"
          >
            Añadir Credencial
          </button>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="cred in reactiveCredentials"
            :key="cred.id"
            class="bg-gradient-to-r from-white/[0.03] to-white/[0.01] border border-white/[0.06] rounded-2xl p-4 flex items-center justify-between group hover:border-white/10 transition-all duration-300"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 group-hover:scale-105 transition-transform duration-300 shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <h4 class="text-white font-semibold text-xs truncate">{{ cred.name }}</h4>
                  <span class="px-1.5 py-0.5 rounded text-[8px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 tracking-wider uppercase">{{ cred.key_identifier }}</span>
                </div>
                <p class="text-[#7a7a7a] text-[11px] mt-0.5 truncate">{{ cred.description || 'Sin descripción' }}</p>
              </div>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <span class="text-[9px] font-mono tracking-wide text-[#444]">••••••••••••</span>
              <button
                @click="deleteReactiveCredential(cred.id)"
                :disabled="deletingId === cred.id"
                class="p-2 text-[#444] hover:text-red-400 transition-colors cursor-pointer rounded-lg hover:bg-red-500/5 disabled:opacity-50"
                title="Eliminar credencial"
              >
                <svg v-if="deletingId === cred.id" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        </div>
      </section>
    </template>

    <!-- Create Modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-[60] flex items-center justify-center animate-fade">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showCreateModal = false"></div>
        
        <div class="relative bg-[#111] border border-white/[0.08] rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.5)] w-full max-w-md mx-4 overflow-hidden">
          <!-- Header -->
          <div class="px-6 py-5 border-b border-white/[0.06] bg-gradient-to-r from-amber-500/5 to-transparent">
            <h2 class="text-sm font-bold text-white flex items-center gap-2.5">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-400"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              Nueva Credencial
            </h2>
            <p class="text-[11px] text-[#666] mt-0.5">El valor se encriptará de forma asimétrica antes de guardarse</p>
          </div>

          <!-- Form -->
          <div class="px-6 py-5 space-y-4">
            <div>
              <label class="block text-[10px] font-bold text-[#666] uppercase tracking-wider mb-1.5">Nombre</label>
              <input
                v-model="form.name"
                type="text"
                placeholder="ej. Correo del Administrador"
                class="w-full px-4 py-2.5 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all duration-200"
              />
            </div>
            <div>
              <label class="block text-[10px] font-bold text-[#666] uppercase tracking-wider mb-1.5">Key Identifier</label>
              <input
                v-model="form.key_identifier"
                type="text"
                placeholder="ej. GMAIL_PASS"
                class="w-full px-4 py-2.5 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all duration-200 font-mono uppercase tracking-wider"
              />
              <p class="text-[9px] text-[#555] mt-1.5 leading-relaxed">El agente usará esta clave para solicitar la credencial durante las automatizaciones</p>
            </div>
            
            <div class="space-y-2.5">
              <div class="flex items-center justify-between mb-1">
                <label class="block text-[10px] font-bold text-[#666] uppercase tracking-wider">Campos (Key-Value)</label>
                <button
                  type="button"
                  @click="addField"
                  class="text-[11px] font-bold text-amber-400 hover:text-amber-300 transition-colors flex items-center gap-1 cursor-pointer"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
                  Añadir campo
                </button>
              </div>
              
              <div v-for="(field, index) in form.fields" :key="index" class="flex items-center gap-2">
                <input
                  v-model="field.key"
                  type="text"
                  placeholder="Key (ej. email)"
                  class="w-1/3 px-3 py-2 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all font-mono"
                />
                <div class="relative flex-1">
                  <input
                    v-model="field.value"
                    :type="field.isSecret ? 'password' : 'text'"
                    placeholder="Valor"
                    class="w-full px-3 py-2 pr-10 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all font-mono"
                  />
                  <button
                    type="button"
                    @click="field.isSecret = !field.isSecret"
                    class="absolute right-2 top-1/2 -translate-y-1/2 text-[#555] hover:text-amber-400 transition-colors cursor-pointer p-1"
                  >
                    <!-- Eye Off -->
                    <svg v-if="field.isSecret" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                    <!-- Eye -->
                    <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                  </button>
                </div>
                <button
                  type="button"
                  @click="removeField(index)"
                  :disabled="form.fields.length <= 1"
                  class="w-9 h-9 flex items-center justify-center shrink-0 rounded-lg text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                </button>
              </div>
            </div>
            
            <div>
              <label class="block text-[10px] font-bold text-[#666] uppercase tracking-wider mb-1.5">Descripción <span class="text-[#444]">(opcional)</span></label>
              <input
                v-model="form.description"
                type="text"
                placeholder="ej. Acceso para el flujo de alertas automáticas"
                class="w-full px-4 py-2.5 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all duration-200"
              />
            </div>
          </div>

          <!-- Actions -->
          <div class="px-6 py-4 border-t border-white/[0.06] flex justify-end gap-3">
            <button
              @click="showCreateModal = false"
              class="px-5 py-2.5 rounded-xl text-[12px] font-semibold text-[#888] hover:bg-white/[0.04] transition-all cursor-pointer"
            >Cancelar</button>
            <button
              @click="createCredential"
              :disabled="isCreating || !form.name.trim() || !form.key_identifier.trim() || !form.fields.some(f => f.key.trim() && f.value.trim())"
              class="px-6 py-2.5 rounded-xl text-[12px] font-bold bg-amber-500 text-[#111] hover:bg-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.2)] transition-all duration-200 flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg v-if="isCreating" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#111]"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              Encriptar y Guardar
            </button>
          </div>
        </div>
      </div>
    </Teleport>
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

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-in {
  animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes fadeInSimple {
  from { opacity: 0; }
  to { opacity: 1; }
}

.animate-fade {
  animation: fadeInSimple 0.2s ease-out forwards;
}
</style>
