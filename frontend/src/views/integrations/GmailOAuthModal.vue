<script setup lang="ts">
import { ref } from 'vue'
import integrationService from '@/services/integrationService'
import { useOAuthCallback } from './oauthCallbackHandler'

const props = defineProps<{
  instanceId: number
}>()

const emit = defineEmits<{
  (e: 'success'): void
  (e: 'error', message: string): void
}>()

const isStarting = ref(false)
const oauthError = ref('')

async function startOAuth() {
  isStarting.value = true
  oauthError.value = ''

  try {
    const { authorization_url } = await integrationService.startOAuth(
      props.instanceId,
      'gmail',
    )

    // Open popup centered
    const width = 500
    const height = 600
    const left = window.screenX + (window.outerWidth - width) / 2
    const top = window.screenY + (window.outerHeight - height) / 2
    const popup = window.open(
      authorization_url,
      'gmail-oauth',
      `width=${width},height=${height},left=${left},top=${top},popup=1`,
    )

    if (!popup) {
      oauthError.value = 'El navegador bloqueó el popup. Permite popups para este sitio.'
      isStarting.value = false
      return
    }

    // Listen for callback
    useOAuthCallback((payload) => {
      isStarting.value = false
      if (payload.type === 'oauth-success') {
        emit('success')
      } else {
        oauthError.value = payload.detail || payload.error_description || payload.error || 'Error desconocido'
        emit('error', oauthError.value)
      }
    })
  } catch (e: any) {
    isStarting.value = false
    oauthError.value = e?.response?.data?.detail || 'Error al iniciar OAuth'
    emit('error', oauthError.value)
  }
}
</script>

<template>
  <div class="space-y-6 text-center">
    <div class="space-y-2">
      <p class="text-[13px] text-[#7a7a7a]">
        Conecta tu cuenta de Gmail para enviar y recibir emails a través del agente.
      </p>
    </div>

    <!-- Error -->
    <div v-if="oauthError" class="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-red-400 text-[12px]">
      {{ oauthError }}
    </div>

    <!-- Sign in with Google -->
    <button
      @click="startOAuth"
      :disabled="isStarting"
      class="w-full py-3 bg-white hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed text-gray-900 font-medium rounded-xl transition-all flex items-center justify-center gap-3 shadow-lg"
    >
      <svg v-if="isStarting" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
      <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
      <span>{{ isStarting ? 'Conectando...' : 'Iniciar sesión con Google' }}</span>
    </button>

    <p class="text-[11px] text-[#4a4a4a]">
      Se abrirá una ventana de Google para autorizar el acceso a tu cuenta de Gmail.
    </p>
  </div>
</template>
