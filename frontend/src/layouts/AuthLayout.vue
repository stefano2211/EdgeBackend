<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="relative w-full h-full min-h-screen flex items-center justify-center bg-gray-950 overflow-hidden">
    <!-- Ambient Background Gradients -->
    <div class="absolute top-[10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-emerald-600/10 blur-[120px] pointer-events-none transition-colors duration-1000"></div>
    <div class="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/15 blur-[120px] pointer-events-none transition-colors duration-1000"></div>

    <RouterView />
  </div>
</template>
