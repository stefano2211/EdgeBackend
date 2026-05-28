<script setup lang="ts">
defineProps<{
  label: string
  description?: string
  modelValue: string | number
  type?: string
  placeholder?: string
}>()

defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()
</script>

<template>
  <div class="py-2">
    <label class="block text-[13px] font-medium text-white mb-2">{{ label }}</label>
    <div class="relative">
      <input
        :type="type || 'text'"
        :value="modelValue"
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        :placeholder="placeholder"
        class="w-full bg-[#2f2f2f] border border-white/[0.08] rounded-xl px-4 py-2.5 text-[13px] text-white placeholder-[#7a7a7a] focus:outline-none focus:border-white/20 transition-colors"
      >
      <slot name="suffix"></slot>
    </div>
    <div v-if="description" class="text-[11px] text-[#7a7a7a] mt-2">{{ description }}</div>
  </div>
</template>
