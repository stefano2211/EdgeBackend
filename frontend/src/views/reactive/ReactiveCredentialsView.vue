<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { reactiveCredentialService, type ReactiveCredential } from '@/services/reactiveCredentialService'

const credentials = ref<ReactiveCredential[]>([])
const isLoading = ref(false)
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

async function loadCredentials() {
  isLoading.value = true
  try {
    credentials.value = await reactiveCredentialService.list()
  } catch (err) {
    console.error('Failed to load credentials', err)
  } finally {
    isLoading.value = false
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
    await loadCredentials()
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

async function deleteCredential(id: number) {
  if (!confirm('¿Eliminar esta credencial permanentemente? El valor encriptado será destruido.')) return
  deletingId.value = id
  try {
    await reactiveCredentialService.remove(id)
    await loadCredentials()
  } catch (err) {
    console.error('Failed to delete credential', err)
  } finally {
    deletingId.value = null
  }
}

function openCreate() {
  form.value = { name: '', key_identifier: '', fields: [{ key: '', value: '', isSecret: true }], description: '' }
  showCreateModal.value = true
}

onMounted(loadCredentials)
</script>

<template>
  <div class="h-full overflow-y-auto">
    <div class="max-w-4xl mx-auto px-8 py-10">
      <!-- Header -->
      <div class="flex items-center justify-between mb-10">
        <div>
          <h1 class="text-[28px] font-bold text-white tracking-tight flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-400"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </div>
            Credenciales
          </h1>
          <p class="text-[13px] text-[#7a7a7a] mt-1.5 ml-[52px]">Contraseñas y secretos encriptados para los agentes autónomos</p>
        </div>
        <button
          @click="openCreate"
          class="px-5 py-2.5 rounded-xl text-[13px] font-bold bg-amber-500 text-[#111] hover:bg-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.2)] hover:shadow-[0_0_25px_rgba(245,158,11,0.4)] hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2 cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
          Nueva Credencial
        </button>
      </div>

      <!-- Security Notice -->
      <div class="mb-8 bg-amber-500/5 border border-amber-500/15 rounded-xl px-5 py-4 flex items-start gap-3">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-400 shrink-0 mt-0.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <div>
          <p class="text-[12px] font-bold text-amber-400 uppercase tracking-wider mb-1">Encriptación AES-256</p>
          <p class="text-[12px] text-[#888] leading-relaxed">Las contraseñas se almacenan encriptadas con Fernet (AES-CBC + HMAC-SHA256). El texto plano <strong class="text-amber-300/80">nunca</strong> se transmite de vuelta al navegador. Solo los agentes pueden desencriptar valores cuando los necesitan durante la ejecución.</p>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="flex items-center justify-center py-20">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin text-amber-400"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
      </div>

      <!-- Empty state -->
      <div v-else-if="credentials.length === 0" class="flex flex-col items-center justify-center py-20 px-8">
        <div class="w-16 h-16 rounded-2xl bg-amber-500/5 border border-amber-500/10 flex items-center justify-center mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-amber-500/40"><path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
        </div>
        <p class="text-[15px] text-[#b4b4b4] font-medium mb-1">Sin credenciales configuradas</p>
        <p class="text-[12px] text-[#555] text-center max-w-sm leading-relaxed">Añade contraseñas para que los agentes puedan iniciar sesión en sistemas web (Gmail, SAP, SCADA) de forma autónoma.</p>
      </div>

      <!-- Credentials list -->
      <div v-else class="space-y-3">
        <div
          v-for="cred in credentials"
          :key="cred.id"
          class="bg-[#111] rounded-xl border border-white/[0.06] hover:border-amber-500/20 transition-all duration-200 px-5 py-4 flex items-center gap-4 group"
        >
          <!-- Icon -->
          <div class="w-10 h-10 rounded-lg bg-amber-500/8 flex items-center justify-center shrink-0 group-hover:bg-amber-500/15 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-400"><path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
          </div>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2.5">
              <span class="text-[14px] font-semibold text-white">{{ cred.name }}</span>
              <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 tracking-wider">{{ cred.key_identifier }}</span>
            </div>
            <div class="flex items-center gap-3 mt-1">
              <span class="text-[11px] text-[#555]">{{ cred.description || 'Sin descripción' }}</span>
              <span class="text-[10px] text-[#3a3a3a]">•</span>
              <span class="text-[11px] text-[#555] font-mono tracking-wide">••••••••••••</span>
            </div>
          </div>

          <!-- Delete -->
          <button
            @click="deleteCredential(cred.id)"
            :disabled="deletingId === cred.id"
            class="px-3 py-2 rounded-lg text-[11px] font-semibold text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-all duration-200 opacity-0 group-hover:opacity-100 cursor-pointer disabled:opacity-50"
          >
            <svg v-if="deletingId === cred.id" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-[60] flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showCreateModal = false"></div>
        <div class="relative bg-[#111] border border-white/[0.08] rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.5)] w-full max-w-md mx-4 overflow-hidden">
          <!-- Header -->
          <div class="px-6 py-5 border-b border-white/[0.06] bg-gradient-to-r from-amber-500/5 to-transparent">
            <h2 class="text-[16px] font-bold text-white flex items-center gap-2.5">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-400"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              Nueva Credencial
            </h2>
            <p class="text-[12px] text-[#666] mt-1">El valor será encriptado antes de almacenarse</p>
          </div>

          <!-- Form -->
          <div class="px-6 py-5 space-y-4">
            <div>
              <label class="block text-[11px] font-bold text-[#888] uppercase tracking-wider mb-1.5">Nombre</label>
              <input
                v-model="form.name"
                type="text"
                placeholder="Gmail de Operaciones"
                class="w-full px-4 py-2.5 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all"
              />
            </div>
            <div>
              <label class="block text-[11px] font-bold text-[#888] uppercase tracking-wider mb-1.5">Key Identifier</label>
              <input
                v-model="form.key_identifier"
                type="text"
                placeholder="GMAIL_PASS"
                class="w-full px-4 py-2.5 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all font-mono uppercase tracking-wider"
              />
              <p class="text-[10px] text-[#555] mt-1">El agente usará este identificador para solicitar la credencial</p>
            </div>
            <div class="space-y-3">
              <div class="flex items-center justify-between mb-1.5">
                <label class="block text-[11px] font-bold text-[#888] uppercase tracking-wider">Campos Secretos (Key-Value)</label>
                <button
                  type="button"
                  @click="addField"
                  class="text-[11px] font-bold text-amber-400 hover:text-amber-300 transition-colors flex items-center gap-1 cursor-pointer"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
                  Añadir
                </button>
              </div>
              
              <div v-for="(field, index) in form.fields" :key="index" class="flex items-center gap-2">
                <input
                  v-model="field.key"
                  type="text"
                  placeholder="ej. email, password"
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
                    class="absolute right-2 top-1/2 -translate-y-1/2 text-[#666] hover:text-amber-400 transition-colors cursor-pointer p-1"
                    title="Alternar visibilidad"
                  >
                    <!-- Eye Off (Secret) -->
                    <svg v-if="field.isSecret" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
                    <!-- Eye (Plaintext) -->
                    <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                  </button>
                </div>
                <button
                  type="button"
                  @click="removeField(index)"
                  :disabled="form.fields.length <= 1"
                  class="w-9 h-9 flex items-center justify-center shrink-0 rounded-lg text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Eliminar campo"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                </button>
              </div>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-[#888] uppercase tracking-wider mb-1.5">Descripción <span class="text-[#444]">(opcional)</span></label>
              <input
                v-model="form.description"
                type="text"
                placeholder="Contraseña de la cuenta erastellius@gmail.com"
                class="w-full px-4 py-2.5 rounded-lg bg-[#0a0a0a] border border-white/[0.08] text-[13px] text-white placeholder:text-[#444] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 outline-none transition-all"
              />
            </div>
          </div>

          <!-- Actions -->
          <div class="px-6 py-4 border-t border-white/[0.06] flex justify-end gap-3">
            <button
              @click="showCreateModal = false"
              class="px-5 py-2.5 rounded-xl text-[13px] font-semibold text-[#888] hover:bg-white/[0.04] transition-all cursor-pointer"
            >Cancelar</button>
            <button
              @click="createCredential"
              :disabled="isCreating || !form.name.trim() || !form.key_identifier.trim() || !form.fields.some(f => f.key.trim() && f.value.trim())"
              class="px-6 py-2.5 rounded-xl text-[13px] font-bold bg-amber-500 text-[#111] hover:bg-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.2)] transition-all duration-200 flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg v-if="isCreating" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#111]"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              Encriptar y Guardar
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
