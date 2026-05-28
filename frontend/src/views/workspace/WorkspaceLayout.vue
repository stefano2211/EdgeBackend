<template>
  <div class="flex flex-col h-full bg-[#0f0f0f] text-[#ececec]">
    <!-- Tab Navigation -->
    <nav class="flex items-center gap-1 px-6 pt-4 pb-0 sticky top-0 bg-[#0f0f0f] z-10 w-full shrink-0 overflow-x-auto no-scrollbar border-b border-white/[0.06]">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="text-[13px] font-medium px-4 py-2.5 -mb-[1px] border-b-2 border-transparent transition-all tracking-tight"
        active-class="!text-white !border-white"
        :class="$route.path.startsWith(tab.path) ? '' : 'text-[#7a7a7a] hover:text-[#b4b4b4]'"
      >
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

<script setup lang="ts">
const tabs = [
  { name: 'Prompts', path: '/workspace/prompts' }
]
</script>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.1s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
