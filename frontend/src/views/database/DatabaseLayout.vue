<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
    { name: 'Conexiones', path: '/database/connections' },
]

function isActive(path: string): boolean {
    return route.path === path || route.path.startsWith(path + '/')
}
</script>

<template>
    <div class="flex flex-col h-full bg-[#0a0a0a] text-[#ececec]">
        <nav class="flex items-center gap-1 px-6 border-b border-white/[0.06]">
            <router-link
                v-for="tab in tabs"
                :key="tab.path"
                :to="tab.path"
                class="px-4 py-3 text-sm font-medium transition-colors border-b-2 border-transparent"
                :class="isActive(tab.path) ? 'text-white border-cyan-400' : 'text-[#7a7a7a] hover:text-[#b4b4b4]'"
            >
                {{ tab.name }}
            </router-link>
        </nav>

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
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
