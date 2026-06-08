<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isProfileOpen = ref(false)

function getInitials(name: string): string {
  if (!name) return 'U'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2 && parts[0]?.[0] && parts[1]?.[0]) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return name[0] ? name[0].toUpperCase() : 'U'
}

function logout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<template>
  <header class="h-14 border-b border-white/[0.06] bg-[#0a0a0a] flex items-center justify-between px-5 shrink-0 sticky top-0 z-30">
    <!-- Left: breadcrumb / title -->
    <div class="flex items-center gap-3">
      <div class="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-white"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      </div>
      <div class="flex items-center gap-2 text-[13px]">
        <span class="text-[#7a7a7a] font-medium">Aura AI</span>
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#444]"><path d="m9 18 6-6-6-6"/></svg>
        <span class="text-white font-medium">Operations Center</span>
      </div>
    </div>

    <!-- Right: actions + avatar -->
    <div class="flex items-center gap-3">
      <!-- Chat button -->
      <button
        @click="router.push('/chat')"
        class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium text-[#b4b4b4] hover:text-white hover:bg-white/5 border border-white/[0.06] hover:border-white/10 transition-all"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
        Chat
      </button>

      <!-- Avatar -->
      <div class="relative">
        <button
          @click="isProfileOpen = !isProfileOpen"
          class="w-8 h-8 rounded-full bg-gradient-to-br from-amber-600 to-orange-700 flex items-center justify-center text-[11px] font-bold text-white shadow-sm hover:ring-2 hover:ring-white/10 transition-all"
        >
          {{ getInitials('Stefano') }}
        </button>

        <Transition name="fade">
          <div v-if="isProfileOpen" class="absolute right-0 top-10 w-48 bg-[#1c1c1c] border border-white/[0.08] rounded-xl shadow-2xl z-50 overflow-hidden">
            <div class="px-3 py-2 border-b border-white/[0.06]">
              <div class="text-[13px] font-medium text-white">Stefano</div>
              <div class="text-[11px] text-[#7a7a7a]">Admin</div>
            </div>
            <div class="py-1">
              <button @click="router.push('/admin/settings'); isProfileOpen = false" class="w-full text-left px-3 py-2 text-[13px] text-[#ececec] hover:bg-white/5 transition-colors flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/></svg>
                Settings
              </button>
            </div>
            <div class="border-t border-white/[0.06] py-1">
              <button @click="logout(); isProfileOpen = false" class="w-full text-left px-3 py-2 text-[13px] text-red-400 hover:bg-white/5 transition-colors flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16,17 21,12 16,7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
                Sign Out
              </button>
            </div>
          </div>
        </Transition>

        <!-- Click outside -->
        <div v-if="isProfileOpen" class="fixed inset-0 z-40" @click="isProfileOpen = false"></div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.12s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
