<script setup lang="ts">
import { ref } from 'vue'
import SettingToggle from './SettingToggle.vue'
import SettingInput from './SettingInput.vue'

// General
const webSearch = ref(false)
const searchEngine = ref('Select a engine')
const bypassEmbedding = ref(false)
const bypassWebLoader = ref(false)
const trustProxy = ref(false)

// Loader
const loaderEngine = ref('Default')
const timeout = ref('')
const verifySSL = ref(true)
const concurrentRequests = ref('10')
const youtubeLanguage = ref('en')
const youtubeProxyUrl = ref('')

function save() {
  alert('Web Search settings saved!')
}
</script>

<template>
  <div class="space-y-8 pb-10">
    
    <!-- General -->
    <div>
      <h3 class="text-[15px] font-semibold text-white mb-4">General</h3>
      
      <div class="space-y-1">
        <SettingToggle 
          label="Web Search" 
          v-model="webSearch" 
        />

        <div class="flex items-center justify-between py-2">
          <div class="text-[13px] font-medium text-white">Web Search Engine</div>
          <select v-model="searchEngine" class="bg-transparent border-none text-[13px] text-[#7a7a7a] focus:outline-none cursor-pointer text-right">
            <option value="Select a engine" class="bg-[#2f2f2f]">Select a engine</option>
            <option value="duckduckgo" class="bg-[#2f2f2f] text-white">DuckDuckGo</option>
            <option value="google" class="bg-[#2f2f2f] text-white">Google</option>
          </select>
        </div>

        <SettingToggle 
          label="Bypass Embedding and Retrieval" 
          v-model="bypassEmbedding" 
        />
        
        <SettingToggle 
          label="Bypass Web Loader" 
          v-model="bypassWebLoader" 
        />

        <SettingToggle 
          label="Trust Proxy Environment" 
          v-model="trustProxy" 
        />
      </div>
    </div>

    <!-- Loader -->
    <div>
      <h3 class="text-[15px] font-semibold text-white mb-4">Loader</h3>
      
      <div class="space-y-1">
        <div class="flex items-center justify-between py-2">
          <div class="text-[13px] font-medium text-white">Web Loader Engine</div>
          <select v-model="loaderEngine" class="bg-transparent border-none text-[13px] text-white focus:outline-none cursor-pointer text-right">
            <option value="Default" class="bg-[#2f2f2f]">Default</option>
          </select>
        </div>

        <div class="flex items-center justify-between py-2">
          <div class="text-[13px] font-medium text-white">Timeout</div>
          <div class="relative w-40">
            <input 
              v-model="timeout"
              type="text" 
              placeholder="Timeout"
              class="w-full bg-transparent border-none text-right text-[13px] text-white placeholder-[#7a7a7a] focus:outline-none"
            >
          </div>
        </div>

        <SettingToggle 
          label="Verify SSL Certificate" 
          v-model="verifySSL" 
        />

        <SettingInput 
          v-model="concurrentRequests"
          label="Concurrent Requests"
          type="number"
        />

        <div class="flex items-center justify-between py-2 mt-4">
          <div class="text-[13px] font-medium text-white">Youtube Language</div>
          <div class="text-[13px] text-white">{{ youtubeLanguage }}</div>
        </div>

        <SettingInput 
          v-model="youtubeProxyUrl"
          label="Youtube Proxy URL"
          placeholder="Enter proxy URL (e.g. https://user:password@host:port)"
        />
      </div>
    </div>

    <!-- Save Button Floating -->
    <div class="fixed bottom-6 right-6">
      <button
        @click="save"
        class="bg-white hover:bg-white/90 text-black text-[14px] font-semibold px-6 py-3 rounded-full shadow-lg transition-transform hover:scale-105"
      >
        Save
      </button>
    </div>
  </div>
</template>
