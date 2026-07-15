<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { name: 'Catálogo', path: '/integrations/catalog', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
  { name: 'Instancias', path: '/integrations/instances', icon: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z' },
  { name: 'Registro', path: '/integrations/registry', icon: 'M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20' },
  { name: 'Credenciales', path: '/integrations/credentials', icon: 'M3 11h18v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V11zm4 0V7a5 5 0 0 1 10 0v4' },
]

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>

<template>
  <div class="flex flex-col h-full bg-[#0a0a0a] text-[#ececec]">
    <!-- Tab Navigation -->
    <nav class="flex items-center gap-1 px-6 pt-4 pb-0 sticky top-0 bg-[#0a0a0a] z-10 w-full shrink-0 overflow-x-auto no-scrollbar border-b border-white/[0.06]">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="text-[13px] font-medium px-4 py-2.5 -mb-[1px] border-b-2 border-transparent transition-all tracking-tight flex items-center gap-2"
        active-class="!text-white !border-white"
        :class="isActive(tab.path) ? '' : 'text-[#7a7a7a] hover:text-[#b4b4b4]'"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path :d="tab.icon"/>
        </svg>
        {{ tab.name }}
      </router-link>
    </nav>

    <!-- Main Content Area -->
    <main class="flex-1 overflow-hidden w-full">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.1s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
