<script setup lang="ts">
defineProps<{
  label: string
  description?: string
  modelValue: boolean
}>()

defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()
</script>

<template>
  <div class="flex items-center justify-between py-2">
    <div>
      <div class="text-[13px] font-medium text-white">{{ label }}</div>
      <div v-if="description" class="text-[12px] text-[#7a7a7a] mt-0.5">{{ description }}</div>
    </div>
    <button
      @click="$emit('update:modelValue', !modelValue)"
      class="relative w-[34px] h-[20px] rounded-full transition-colors shrink-0 outline-none"
      :class="modelValue ? 'bg-[#3fb874]' : 'bg-[#404040]'"
    >
      <div
        class="absolute top-[2px] left-[2px] w-[16px] h-[16px] bg-white rounded-full transition-transform shadow-sm"
        :class="modelValue ? 'translate-x-[14px]' : 'translate-x-0'"
      ></div>
    </button>
  </div>
</template>
