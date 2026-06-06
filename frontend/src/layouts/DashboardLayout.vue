<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import DashboardNavbar from '@/components/dashboard/DashboardNavbar.vue'

const route = useRoute()
const router = useRouter()

interface NavItem {
  label: string
  path: string
  icon: string
}

const navItems: NavItem[] = [
  {
    label: 'Operations',
    path: '/events',
    icon: 'M13 2 3 14h9l-1 8 10-12h-9l1-8z'
  },
  {
    label: 'Integraciones',
    path: '/integrations',
    icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5'
  },
  {
    label: 'Bases de Datos',
    path: '/database',
    icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5l0 6m0-6l-2-2m2 2l2 2'
  },
  {
    label: 'Conocimiento',
    path: '/reactive/knowledge',
    icon: 'M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20'
  },
  {
    label: 'Webhooks',
    path: '/settings/webhooks',
    icon: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z'
  },
  {
    label: 'Admin',
    path: '/events?admin=users',
    icon: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm10 0h.01M19 12h.01M19 17h.01'
  }
]

function isActive(path: string): boolean {
  if (path.includes('?')) {
    const [basePath, queryStr] = path.split('?')
    const params = new URLSearchParams(queryStr)
    const matchesBase = route.path === basePath
    for (const [key, value] of params.entries()) {
      if (route.query[key] !== value) return false
    }
    return matchesBase
  }

  if (path === '/events' && route.query.admin) {
    return false
  }

  return route.path === path || route.path.startsWith(path + '/')
}
</script>

<template>
  <div class="h-screen w-screen bg-[#0a0a0a] text-white flex overflow-hidden">
    <!-- Left sidebar -->
    <aside class="w-14 border-r border-white/[0.06] bg-[#0a0a0a] flex flex-col items-center py-4 gap-1 shrink-0">
      <!-- Logo -->
      <div class="mb-4 w-8 h-8 rounded-lg bg-white flex items-center justify-center shrink-0">
        <span class="text-black font-bold text-xs">A</span>
      </div>

      <!-- Nav icons -->
      <button
        v-for="item in navItems"
        :key="item.path"
        @click="router.push(item.path)"
        class="w-10 h-10 rounded-lg flex items-center justify-center transition-all group relative"
        :class="[
          isActive(item.path)
            ? item.path === '/database'
              ? 'bg-cyan-400/20 text-cyan-400'
              : 'bg-white/10 text-white'
            : item.path === '/database'
              ? 'text-[#666] hover:text-cyan-400 hover:bg-cyan-400/5'
              : 'text-[#666] hover:text-white hover:bg-white/5'
        ]"
        :title="item.label"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path :d="item.icon"/>
        </svg>

        <!-- Tooltip -->
        <div class="absolute left-full ml-2 px-2 py-1 bg-[#1c1c1c] border border-white/[0.08] rounded-md text-[11px] text-white whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
          {{ item.label }}
        </div>
      </button>

      <!-- Spacer -->
      <div class="flex-1"></div>

      <!-- Bottom: Chat shortcut -->
      <button
        @click="router.push('/chat')"
        class="w-10 h-10 rounded-lg flex items-center justify-center text-[#666] hover:text-white hover:bg-white/5 transition-all group relative"
        title="Open Chat"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
        <div class="absolute left-full ml-2 px-2 py-1 bg-[#1c1c1c] border border-white/[0.08] rounded-md text-[11px] text-white whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
          Chat
        </div>
      </button>
    </aside>

    <!-- Main area -->
    <div class="flex-1 flex flex-col min-w-0">
      <DashboardNavbar />
      <main class="flex-1 overflow-auto">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
/* No scrollbar for sidebar */
aside::-webkit-scrollbar { display: none; }
aside { -ms-overflow-style: none; scrollbar-width: none; }
</style>
