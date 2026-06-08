<script setup lang="ts">
import { ref, computed } from 'vue'

import SettingsGeneral from '@/components/admin/settings/SettingsGeneral.vue'
import SettingsProviders from '@/components/admin/settings/SettingsProviders.vue'
import SettingsDocuments from '@/components/admin/settings/SettingsDocuments.vue'
import SettingsWebSearch from '@/components/admin/settings/SettingsWebSearch.vue'

const settingsTabs = [
  { id: 'general', label: 'General', icon: 'settings', component: SettingsGeneral },
  { id: 'providers', label: 'Providers', icon: 'cpu', component: SettingsProviders },
  { id: 'documents', label: 'Documents', icon: 'file', component: SettingsDocuments },
  { id: 'web-search', label: 'Web Search', icon: 'globe', component: SettingsWebSearch },
]

const activeSettingsTabId = ref('general')
const activeSettingsTab = computed(() => settingsTabs.find(t => t.id === activeSettingsTabId.value) || settingsTabs[0])
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="flex-1 flex overflow-hidden min-h-[400px]">
      <!-- Settings Sidebar -->
      <div class="w-48 shrink-0 bg-white/[0.01] border-r border-white/[0.06] p-4 flex flex-col gap-0.5">
        <button
          v-for="tab in settingsTabs"
          :key="tab.id"
          @click="activeSettingsTabId = tab.id"
          class="flex items-center gap-2.5 w-full px-3 py-2 text-[12px] font-medium rounded-lg transition-colors text-left"
          :class="activeSettingsTabId === tab.id
            ? 'bg-white/5 text-white shadow-sm border border-white/5'
            : 'text-[#7a7a7a] hover:text-[#b4b4b4] hover:bg-white/[0.02] border border-transparent'"
        >
          <!-- settings icon -->
          <svg v-if="tab.icon === 'settings'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06-.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          <!-- cpu icon -->
          <svg v-else-if="tab.icon === 'cpu'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>
          <!-- file icon -->
          <svg v-else-if="tab.icon === 'file'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>
          <!-- globe icon -->
          <svg v-else-if="tab.icon === 'globe'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/><path d="M2 12h20"/></svg>

          {{ tab.label }}
        </button>
      </div>

      <!-- Settings Content Pane -->
      <div class="flex-1 p-6 overflow-y-auto no-scrollbar pb-16">
        <h3 class="text-sm font-semibold text-white mb-4 border-b border-white/[0.04] pb-2">{{ activeSettingsTab?.label }} Configuration</h3>
        <component 
          v-if="activeSettingsTab"
          :is="activeSettingsTab.component" 
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
