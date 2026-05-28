<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AuthLayout from './layouts/AuthLayout.vue'
import MainLayout from './layouts/MainLayout.vue'
import DashboardLayout from './layouts/DashboardLayout.vue'
import { cleanupOAuthCallback } from './views/integrations/oauthCallbackHandler'

const route = useRoute()

onMounted(() => {
  // Ensure any stale OAuth callback listeners are cleaned up on app load
  cleanupOAuthCallback()
})

// Map layout names to actual components
const layoutComponent = computed(() => {
  if (route.meta.layout === 'auth') return AuthLayout
  if (route.meta.layout === 'main') return MainLayout
  if (route.meta.layout === 'dashboard') return DashboardLayout
  // Fallback to minimal wrapper if no layout specified
  return 'div'
})
</script>

<template>
  <component :is="layoutComponent" v-if="route.meta.layout">
    <RouterView />
  </component>
  
  <RouterView v-else />
</template>

<style>
/* Global resets handled by Tailwind */
</style>
