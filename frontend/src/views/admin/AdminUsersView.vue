<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { adminService, type AdminUser } from '@/services/adminService'

const users = ref<AdminUser[]>([])
const userSearchQuery = ref('')
const isUsersLoading = ref(true)

const filteredUsers = computed(() => {
  if (!userSearchQuery.value) return users.value
  const q = userSearchQuery.value.toLowerCase()
  return users.value.filter(u =>
    u.username.toLowerCase().includes(q) ||
    u.email.toLowerCase().includes(q)
  )
})

async function loadUsers() {
  isUsersLoading.value = true
  try {
    users.value = await adminService.listUsers()
  } catch (e) {
    console.error('Failed to load users', e)
  } finally {
    isUsersLoading.value = false
  }
}

async function toggleRole(user: AdminUser) {
  try {
    const updated = await adminService.updateUserRole(user.id, !user.is_superuser)
    const idx = users.value.findIndex(u => u.id === user.id)
    if (idx !== -1) users.value[idx] = updated
  } catch (e) {
    console.error('Failed to update role', e)
  }
}

async function deleteUser(user: AdminUser) {
    if (!confirm(`¿Estás seguro de eliminar a ${user.username}?`)) return
  try {
    await adminService.deleteUser(user.id)
    users.value = users.value.filter(u => u.id !== user.id)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Error al eliminar usuario')
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

onMounted(() => {
  loadUsers()
})
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-base font-semibold text-white">
        Usuarios <span class="text-[#7a7a7a] font-normal text-sm ml-1">{{ users.length }}</span>
      </h2>
      <!-- Search -->
      <div class="relative">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="absolute left-3 top-1/2 -translate-y-1/2 text-[#7a7a7a]"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <input
          v-model="userSearchQuery"
          type="text"
          placeholder="Buscar usuarios..."
          class="bg-white/5 border border-white/[0.06] rounded-xl pl-9 pr-4 py-1.5 text-[12px] text-white placeholder-[#7a7a7a] w-56 focus:outline-none focus:border-white/20 transition-colors"
        >
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isUsersLoading" class="flex items-center justify-center py-20 text-[#7a7a7a] text-sm">
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin mr-2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
      Cargando usuarios...
    </div>

    <!-- Users Table -->
    <div v-else class="bg-white/[0.02] rounded-2xl border border-white/[0.06] overflow-hidden">
      <!-- Table Header -->
      <div class="grid grid-cols-[110px_1fr_1.2fr_130px_130px_50px] gap-4 px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-[#7a7a7a] border-b border-white/[0.06]">
        <div>Rol</div>
        <div>Nombre</div>
        <div>Correo electrónico</div>
        <div>Última actividad</div>
        <div>Creado</div>
        <div></div>
      </div>

      <!-- Rows -->
      <template v-if="filteredUsers.length > 0">
        <div
          v-for="user in filteredUsers"
          :key="user.id"
          class="grid grid-cols-[110px_1fr_1.2fr_130px_130px_50px] gap-4 px-5 py-3.5 items-center border-b border-white/[0.04] last:border-0 hover:bg-white/[0.02] transition-colors"
        >
          <!-- Role Badge -->
          <div>
            <button
              @click="toggleRole(user)"
              class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide transition-colors cursor-pointer"
              :class="user.is_superuser 
                ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20 hover:bg-sky-500/20' 
                : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20'"
              title="Clic para cambiar rol"
            >
              {{ user.is_superuser ? 'ADMIN' : 'USUARIO' }}
            </button>
          </div>

          <!-- Name -->
          <div class="flex items-center gap-2.5 min-w-0">
            <div class="w-6 h-6 rounded-full bg-gradient-to-br from-gray-500 to-gray-700 flex items-center justify-center shrink-0 text-[10px] font-bold text-white uppercase">
              {{ user.username[0] }}
            </div>
            <span class="text-[13px] text-white font-medium truncate">{{ user.username }}</span>
            <div v-if="user.is_active" class="w-1.5 h-1.5 bg-green-500 rounded-full shrink-0" title="Activo"></div>
          </div>

          <!-- Email -->
          <div class="text-[12px] text-[#b4b4b4] truncate">{{ user.email }}</div>

          <!-- Last Active -->
          <div class="text-[12px] text-[#7a7a7a] truncate">{{ timeAgo(user.updated_at) }}</div>

          <!-- Created At -->
          <div class="text-[12px] text-[#7a7a7a] truncate">{{ formatDate(user.created_at) }}</div>

          <!-- Actions -->
          <div class="flex justify-end">
            <button
              @click="deleteUser(user)"
              class="p-1 text-[#7a7a7a] hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              title="Eliminar usuario"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </template>

      <!-- Empty state -->
      <div v-else class="px-5 py-12 text-center text-[#7a7a7a] text-[13px]">
        No se encontraron usuarios.
      </div>
    </div>
    <p class="text-[11px] text-[#555] mt-3 text-center">
      ⓘ Haz clic en el rol de un usuario para cambiar sus permisos.
    </p>
  </div>
</template>
