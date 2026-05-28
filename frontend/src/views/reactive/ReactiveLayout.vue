<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const navItems = [
  {
    label: 'Conocimiento',
    path: '/reactive/knowledge',
    icon: 'M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20',
    color: 'emerald'
  },
]

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}

function getNavItemClasses(item: any) {
  const active = isActive(item.path)
  if (!active) return 'text-[#7a7a7a] hover:bg-white/[0.04] hover:text-white'
  
  if (item.color === 'emerald') {
    return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
  }
  if (item.color === 'amber') {
    return 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
  }
  return 'bg-violet-500/10 text-violet-300 border border-violet-500/20'
}
</script>

<template>
  <div class="flex h-full bg-[#0a0a0a] text-white overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-[240px] shrink-0 bg-[#0d0d0d] border-r border-white/[0.06] flex flex-col relative z-20">
      <!-- Glow effect for sidebar -->
      <div class="absolute left-0 top-0 w-full h-64 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none"></div>

      <div class="px-6 py-8 relative z-10">
        <h1 class="text-[11px] font-bold text-[#4a4a4a] uppercase tracking-[0.2em] mb-1">Configuración</h1>
        <div class="text-[16px] font-bold text-white tracking-tight">Sistema Reactivo</div>
      </div>

      <nav class="flex-1 px-3 py-2 space-y-1 relative z-10">
        <button
          v-for="item in navItems"
          :key="item.path"
          @click="router.push(item.path)"
          class="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-[13px] font-semibold transition-all text-left group"
          :class="getNavItemClasses(item)"
        >
          <div class="w-8 h-8 rounded-lg flex items-center justify-center transition-all" 
            :class="isActive(item.path) ? (item.color === 'emerald' ? 'bg-emerald-500/20' : item.color === 'amber' ? 'bg-amber-500/20' : 'bg-violet-500/20') : 'bg-white/[0.03] group-hover:bg-white/[0.08]'">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path :d="item.icon"/>
            </svg>
          </div>
          {{ item.label }}
        </button>
      </nav>

      <!-- Back to Events -->
      <div class="px-4 py-6 border-t border-white/[0.03] relative z-10">
        <button
          @click="router.push('/events')"
          class="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-[13px] font-medium transition-all text-left text-[#4a4a4a] hover:bg-white/[0.03] hover:text-white group"
        >
          <div class="w-8 h-8 rounded-lg bg-white/[0.02] flex items-center justify-center group-hover:bg-white/[0.05]">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="m15 18-6-6 6-6"/>
            </svg>
          </div>
          Volver a Operaciones
        </button>
      </div>
    </aside>

    <!-- Content -->
    <main class="flex-1 overflow-hidden relative z-10 bg-[#0a0a0a]">
      <router-view v-slot="{ Component }">
        <transition 
          name="fade" 
          mode="out-in"
          enter-active-class="transition duration-300 ease-out"
          enter-from-class="opacity-0 translate-x-4"
          enter-to-class="opacity-100 translate-x-0"
          leave-active-class="transition duration-200 ease-in"
          leave-from-class="opacity-100 translate-x-0"
          leave-to-class="opacity-0 -translate-x-4"
        >
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
/* Smooth transitions for sidebar items */
button {
  backface-visibility: hidden;
  transform: translateZ(0);
}
</style>
