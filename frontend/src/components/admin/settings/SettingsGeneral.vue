<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SettingToggle from './SettingToggle.vue'
import { adminService, type SystemSettingsGeneral } from '@/services/adminService'

const isLoading = ref(true)
const isSaving = ref(false)

// Configuración General
const defaultUserRole = ref('pending')
const enableSignUps = ref(true)

// Features
const enableApiKeys = ref(true)
const jwtExpiration = ref('4w')
const enableCommunitySharing = ref(true)

onMounted(async () => {
  try {
    const settings = await adminService.getGeneralSettings()
    defaultUserRole.value = settings.auth_default_user_role
    enableSignUps.value = settings.auth_enable_sign_ups
    enableApiKeys.value = settings.feature_enable_api_keys
    jwtExpiration.value = settings.feature_jwt_expiration
    enableCommunitySharing.value = settings.feature_enable_community_sharing
  } catch (error) {
    console.error('Failed to load general settings:', error)
  } finally {
    isLoading.value = false
  }
})

async function save() {
  if (isSaving.value) return
  isSaving.value = true
  
  try {
    const payload: SystemSettingsGeneral = {
      auth_default_user_role: defaultUserRole.value,
      auth_enable_sign_ups: enableSignUps.value,
      feature_enable_api_keys: enableApiKeys.value,
      feature_jwt_expiration: jwtExpiration.value,
      feature_enable_community_sharing: enableCommunitySharing.value
    }
    
    await adminService.updateGeneralSettings(payload)
    alert('General settings saved successfully')
  } catch (error) {
    console.error('Failed to save settings:', error)
    alert('Failed to save General settings')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="space-y-8 pb-10 relative">
    
    <div v-if="isLoading" class="absolute inset-0 z-10 bg-[#212121]/80 backdrop-blur-sm flex items-center justify-center">
      <div class="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Version & Help -->
    <div class="grid grid-cols-[200px_1fr] gap-4">
      <div>
        <div class="text-[14px] font-semibold text-white mb-1">Version</div>
        <div class="text-[13px] text-[#b4b4b4]">v0.8.8 (v0.8.10 available!)</div>
        <a href="#" class="text-[12px] text-[#7a7a7a] hover:text-white underline underline-offset-2">See what's new</a>
      </div>
      <div class="flex justify-end items-start mt-2">
        <button class="bg-[#2f2f2f] hover:bg-[#3f3f3f] text-white text-[13px] font-medium px-4 py-2 rounded-xl transition-colors border border-white/[0.06]">
          Check for updates
        </button>
      </div>
    </div>

    <!-- General Settings -->
    <div>
      <h3 class="text-[15px] font-semibold text-white mb-4">Authentication Configuration</h3>
      <div class="space-y-1">
        <SettingToggle 
          label="Enable New Sign Ups" 
          v-model="enableSignUps" 
        />
        <div class="flex items-center justify-between py-2">
          <div class="text-[13px] font-medium text-white">Default User Role</div>
          <select v-model="defaultUserRole" class="bg-transparent border-none text-[13px] text-white focus:outline-none cursor-pointer text-right">
            <option value="pending" class="bg-[#2f2f2f]">Pending</option>
            <option value="user" class="bg-[#2f2f2f]">User</option>
            <option value="admin" class="bg-[#2f2f2f]">Admin</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Features Settings -->
    <div>
      <h3 class="text-[15px] font-semibold text-white mb-4">Global Features</h3>
      <div class="space-y-1">
        <SettingToggle 
          label="Enable API Keys" 
          v-model="enableApiKeys" 
        />
        <SettingToggle 
          label="Enable Community Sharing" 
          v-model="enableCommunitySharing" 
        />
        <div class="flex items-center justify-between py-2 mt-4">
          <div class="text-[13px] font-medium text-white">JWT Expiration</div>
          <select v-model="jwtExpiration" class="bg-transparent border-none text-[13px] text-white focus:outline-none cursor-pointer text-right">
            <option value="1h" class="bg-[#2f2f2f]">1 Hour</option>
            <option value="1d" class="bg-[#2f2f2f]">1 Day</option>
            <option value="1w" class="bg-[#2f2f2f]">1 Week</option>
            <option value="4w" class="bg-[#2f2f2f]">4 Weeks</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Additional Information -->
    <div class="text-[#7a7a7a] text-[13px] py-6 border border-dashed border-white/[0.08] rounded-2xl flex flex-col items-center justify-center text-center px-6">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mb-3 opacity-50"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      These settings affect global authentication and availability features.<br/>
      Disabling Sign Ups immediately blocks any new user registration except manually created ones.
    </div>

    <!-- Save Button -->
    <div class="fixed bottom-6 right-6">
      <button
        @click="save"
        :disabled="isLoading || isSaving"
        class="bg-white hover:bg-white/90 text-black text-[14px] font-semibold px-6 py-3 rounded-full shadow-lg transition-transform hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 flex items-center gap-2"
      >
        <span v-if="isSaving" class="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin inline-block"></span>
        {{ isSaving ? 'Saving...' : 'Save' }}
      </button>
    </div>
  </div>
</template>
