<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { webhookService, type WebhookSource, type WebhookTestResult } from '@/services/webhookService'

// ── State ─────────────────────────────────────────────────────────────────────
const webhooks = ref<WebhookSource[]>([])
const isLoading = ref(false)
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showTestModal = ref(false)
const selectedWebhook = ref<WebhookSource | null>(null)

// Create form
const createForm = ref({
  name: '',
  slug: '',
  description: '',
  rate_limit_rpm: 60,
})
const isCreating = ref(false)
const createError = ref('')

// Edit form
const editForm = ref<Partial<WebhookSource>>({})
const isSaving = ref(false)
const editError = ref('')

// Test panel
const testPayload = ref('')
const testResult = ref<WebhookTestResult | null>(null)
const isTesting = ref(false)
const testError = ref('')

// Copy feedback
const copiedSlug = ref<string | null>(null)

// ── Computed ──────────────────────────────────────────────────────────────────
const baseUrl = computed(() => {
  return import.meta.env.VITE_API_URL || window.location.origin
})

function webhookUrl(slug: string) {
  return `${baseUrl.value}/webhooks/${slug}/receive`
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadWebhooks() {
  isLoading.value = true
  try {
    webhooks.value = await webhookService.list()
  } catch (err) {
    console.error('Failed to load webhooks', err)
  } finally {
    isLoading.value = false
  }
}

// ── Create ────────────────────────────────────────────────────────────────────
function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function onNameInput() {
  if (!createForm.value.slug) {
    createForm.value.slug = generateSlug(createForm.value.name)
  }
}

async function createWebhook() {
  if (!createForm.value.name.trim() || !createForm.value.slug.trim()) return
  isCreating.value = true
  createError.value = ''
  try {
    await webhookService.create({
      name: createForm.value.name,
      slug: createForm.value.slug,
      description: createForm.value.description || undefined,
      rate_limit_rpm: createForm.value.rate_limit_rpm,
    })
    showCreateModal.value = false
    resetCreateForm()
    await loadWebhooks()
  } catch (err: any) {
    createError.value = err.response?.data?.detail || 'Failed to create webhook'
  } finally {
    isCreating.value = false
  }
}

function resetCreateForm() {
  createForm.value = { name: '', slug: '', description: '', rate_limit_rpm: 60 }
}

// ── Edit ──────────────────────────────────────────────────────────────────────
function openEdit(webhook: WebhookSource) {
  selectedWebhook.value = webhook
  editForm.value = {
    name: webhook.name,
    description: webhook.description,
    is_enabled: webhook.is_enabled,
    rate_limit_rpm: webhook.rate_limit_rpm,
    domain: webhook.domain,
    mapping_config: webhook.mapping_config ? JSON.parse(JSON.stringify(webhook.mapping_config)) : null,
  }
  showEditModal.value = true
  editError.value = ''
}

async function saveEdit() {
  if (!selectedWebhook.value) return
  isSaving.value = true
  editError.value = ''
  try {
    await webhookService.update(selectedWebhook.value.slug, editForm.value)
    showEditModal.value = false
    await loadWebhooks()
  } catch (err: any) {
    editError.value = err.response?.data?.detail || 'Failed to update webhook'
  } finally {
    isSaving.value = false
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────
async function deleteWebhook(webhook: WebhookSource) {
  if (!confirm(`Delete webhook "${webhook.name}"? This cannot be undone.`)) return
  try {
    await webhookService.delete(webhook.slug)
    await loadWebhooks()
  } catch (err) {
    console.error('Failed to delete webhook', err)
    alert('Failed to delete webhook')
  }
}

// ── Test ──────────────────────────────────────────────────────────────────────
function openTest(webhook: WebhookSource) {
  selectedWebhook.value = webhook
  testPayload.value = JSON.stringify({
    alert: {
      title: 'Test Alert',
      body: 'This is a test payload',
      priority: 'warning',
      type: 'test',
      timestamp: new Date().toISOString()
    }
  }, null, 2)
  testResult.value = null
  testError.value = ''
  showTestModal.value = true
}

async function runTest() {
  if (!selectedWebhook.value) return
  isTesting.value = true
  testError.value = ''
  testResult.value = null
  try {
    let payload: any
    try {
      payload = JSON.parse(testPayload.value)
    } catch {
      testError.value = 'Invalid JSON in payload'
      return
    }
    testResult.value = await webhookService.test(selectedWebhook.value.slug, payload)
  } catch (err: any) {
    testError.value = err.response?.data?.detail || 'Test failed'
  } finally {
    isTesting.value = false
  }
}

// ── Copy URL ──────────────────────────────────────────────────────────────────
async function copyUrl(slug: string) {
  try {
    await navigator.clipboard.writeText(webhookUrl(slug))
    copiedSlug.value = slug
    setTimeout(() => copiedSlug.value = null, 2000)
  } catch {
    // Fallback
    const input = document.createElement('input')
    input.value = webhookUrl(slug)
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    copiedSlug.value = slug
    setTimeout(() => copiedSlug.value = null, 2000)
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatDate(d: string | null) {
  if (!d) return 'Never'
  return new Date(d).toLocaleString('es', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function truncatePreview(obj: any, maxLen = 200): string {
  const str = JSON.stringify(obj)
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen) + '...'
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  loadWebhooks()
})
</script>

<template>
  <div class="h-full bg-[#0a0a0a] text-white overflow-y-auto">
    <!-- Header -->
    <div class="px-6 py-5 border-b border-white/[0.06] flex items-center justify-between">
      <div>
        <h1 class="text-[18px] font-semibold text-white">Webhooks</h1>
        <p class="text-[13px] text-[#7a7a7a] mt-0.5">
          Configure inbound webhooks to receive events from any external system.
        </p>
      </div>
      <button
        @click="showCreateModal = true"
        class="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-[13px] font-medium transition-colors flex items-center gap-2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
        New Webhook
      </button>
    </div>

    <!-- Loading -->
    <div v-if="isLoading && webhooks.length === 0" class="flex items-center justify-center h-64 text-[#7a7a7a]">
      <svg class="animate-spin mr-2" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
      Loading webhooks...
    </div>

    <!-- Empty state -->
    <div v-else-if="webhooks.length === 0" class="flex flex-col items-center justify-center h-64 text-[#7a7a7a] gap-3">
      <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      <p class="text-sm">No webhooks configured yet</p>
      <button @click="showCreateModal = true" class="text-violet-400 hover:text-violet-300 text-[13px]">Create your first webhook</button>
    </div>

    <!-- List -->
    <div v-else class="p-6 space-y-3">
      <div
        v-for="wh in webhooks"
        :key="wh.id"
        class="bg-[#111] border border-white/[0.06] rounded-xl p-5 transition-all hover:border-white/[0.1]"
      >
        <div class="flex items-start justify-between gap-4">
          <!-- Left: Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1.5 flex-wrap">
              <h3 class="text-[15px] font-semibold text-white">{{ wh.name }}</h3>
              <span
                class="px-2 py-0.5 rounded text-[10px] font-bold uppercase border"
                :class="wh.is_enabled
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-white/5 text-[#555] border-white/10'"
              >
                {{ wh.is_enabled ? 'Enabled' : 'Disabled' }}
              </span>
              <span v-if="wh.auto_discovered" class="px-2 py-0.5 rounded text-[10px] font-bold uppercase border bg-purple-500/10 text-purple-400 border-purple-500/20">
                Auto-discovered
              </span>
              <span
                v-if="wh.domain"
                class="px-2 py-0.5 rounded text-[10px] font-bold uppercase border bg-blue-500/10 text-blue-400 border-blue-500/20"
                :title="wh.domain ? `Domain: ${wh.domain}` : 'Domain will be auto-detected from first event'"
              >
                {{ wh.domain }}
              </span>
              <span
                v-else
                class="px-2 py-0.5 rounded text-[10px] font-bold uppercase border bg-white/5 text-[#555] border-white/10"
                title="Domain will be auto-detected from the first event received"
              >
                Auto
              </span>
            </div>

            <p v-if="wh.description" class="text-[12px] text-[#7a7a7a] mb-2">{{ wh.description }}</p>

            <!-- URL -->
            <div class="flex items-center gap-2 mb-2">
              <code class="text-[11px] text-[#a0a0a0] font-mono bg-white/5 px-2 py-1 rounded border border-white/[0.06] truncate flex-1">
                POST {{ webhookUrl(wh.slug) }}
              </code>
              <button
                @click="copyUrl(wh.slug)"
                class="p-1.5 hover:bg-white/8 rounded-lg transition-colors text-[#7a7a7a] hover:text-white shrink-0"
                :title="copiedSlug === wh.slug ? 'Copied!' : 'Copy URL'"
              >
                <svg v-if="copiedSlug === wh.slug" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400"><path d="M20 6L9 17l-5-5"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
              </button>
            </div>

            <!-- Stats -->
            <div class="flex items-center gap-4 text-[11px] text-[#7a7a7a]">
              <span>Received: <span class="text-[#ececec]">{{ wh.total_received.toLocaleString() }}</span></span>
              <span>Rate limit: <span class="text-[#ececec]">{{ wh.rate_limit_rpm }}</span>/min</span>
              <span>Last: <span class="text-[#ececec]">{{ formatDate(wh.last_received_at) }}</span></span>
            </div>
          </div>

          <!-- Right: Actions -->
          <div class="flex items-center gap-1 shrink-0">
            <button
              @click="openTest(wh)"
              class="p-2 hover:bg-white/8 rounded-lg transition-colors text-[#7a7a7a] hover:text-white"
              title="Test mapping"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
            </button>
            <button
              @click="openEdit(wh)"
              class="p-2 hover:bg-white/8 rounded-lg transition-colors text-[#7a7a7a] hover:text-white"
              title="Edit"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
            </button>
            <button
              @click="deleteWebhook(wh)"
              class="p-2 hover:bg-red-500/10 rounded-lg transition-colors text-[#7a7a7a] hover:text-red-400"
              title="Delete"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="showCreateModal = false">
        <div class="bg-[#141414] border border-white/[0.1] rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
          <div class="px-6 pt-5 pb-0">
            <h3 class="text-[16px] font-semibold text-white mb-4 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-violet-400"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              New Webhook
            </h3>
          </div>
          <div class="px-6 py-4 space-y-3">
            <div>
              <label class="text-[12px] text-[#7a7a7a] mb-1 block">Name *</label>
              <input
                v-model="createForm.name"
                @input="onNameInput"
                type="text"
                placeholder="e.g. SCADA Plant A"
                class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] placeholder-[#555] focus:outline-none focus:border-violet-500/50"
              />
            </div>
            <div>
              <label class="text-[12px] text-[#7a7a7a] mb-1 block">Slug * <span class="text-[#555]">(URL-safe identifier)</span></label>
              <input
                v-model="createForm.slug"
                type="text"
                placeholder="e.g. scada-plant-a"
                class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] placeholder-[#555] focus:outline-none focus:border-violet-500/50 font-mono"
              />
            </div>
            <div>
              <label class="text-[12px] text-[#7a7a7a] mb-1 block">Description</label>
              <textarea
                v-model="createForm.description"
                rows="2"
                placeholder="Optional description..."
                class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] placeholder-[#555] focus:outline-none focus:border-violet-500/50 resize-none"
              />
            </div>
            <div>
              <label class="text-[12px] text-[#7a7a7a] mb-1 block">Rate Limit (requests/min)</label>
              <input
                v-model.number="createForm.rate_limit_rpm"
                type="number"
                min="1"
                max="10000"
                class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] focus:outline-none focus:border-violet-500/50"
              />
            </div>
            <p v-if="createError" class="text-[12px] text-red-400 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">{{ createError }}</p>
          </div>
          <div class="px-6 py-4 bg-white/[0.02] border-t border-white/[0.06] flex justify-end gap-2">
            <button @click="showCreateModal = false" class="px-4 py-2 text-[13px] text-[#7a7a7a] hover:text-white transition-colors">Cancel</button>
            <button
              @click="createWebhook"
              :disabled="isCreating || !createForm.name.trim() || !createForm.slug.trim()"
              class="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg v-if="isCreating" class="animate-spin inline mr-1" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              Create Webhook
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Edit Modal -->
    <Teleport to="body">
      <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="showEditModal = false">
        <div class="bg-[#141414] border border-white/[0.1] rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
          <div class="px-6 pt-5 pb-0 shrink-0">
            <h3 class="text-[16px] font-semibold text-white mb-1 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-violet-400"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
              Edit Webhook
            </h3>
            <p class="text-[12px] text-[#555] mb-4">{{ selectedWebhook?.slug }}</p>
          </div>
          <div class="px-6 py-4 space-y-3 overflow-y-auto flex-1">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="text-[12px] text-[#7a7a7a] mb-1 block">Name</label>
                <input v-model="editForm.name" type="text" class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] focus:outline-none focus:border-violet-500/50" />
              </div>
              <div>
                <label class="text-[12px] text-[#7a7a7a] mb-1 block">Rate Limit (req/min)</label>
                <input v-model.number="editForm.rate_limit_rpm" type="number" min="1" max="10000" class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] focus:outline-none focus:border-violet-500/50" />
              </div>
            </div>
            <div>
              <label class="text-[12px] text-[#7a7a7a] mb-1 block">Description</label>
              <textarea v-model="editForm.description" rows="2" class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] focus:outline-none focus:border-violet-500/50 resize-none" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="flex items-center gap-2">
                <label class="text-[12px] text-[#7a7a7a]">Enabled</label>
                <button
                  @click="editForm.is_enabled = !editForm.is_enabled"
                  class="relative w-9 h-5 rounded-full transition-colors"
                  :class="editForm.is_enabled ? 'bg-violet-600' : 'bg-white/10'"
                >
                  <span class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform" :class="editForm.is_enabled ? 'translate-x-4' : 'translate-x-0'" />
                </button>
              </div>
              <div>
                <label class="text-[12px] text-[#7a7a7a] mb-1 block">Domain</label>
                <select
                  v-model="editForm.domain"
                  class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[14px] text-[#ececec] focus:outline-none focus:border-violet-500/50"
                >
                  <option :value="null">Auto-detect</option>
                  <option value="manufacturing">Manufacturing</option>
                  <option value="healthcare">Healthcare</option>
                  <option value="logistics">Logistics</option>
                  <option value="energy">Energy</option>
                  <option value="it_operations">IT Operations</option>
                  <option value="finance">Finance</option>
                  <option value="generic">Generic</option>
                </select>
                <p class="text-[10px] text-[#555] mt-1">Auto-detect: learned from first event</p>
              </div>
            </div>
            <div>
              <label class="text-[12px] text-[#7a7a7a] mb-1 block flex items-center justify-between">
                <span>Mapping Config (JSON)</span>
                <span class="text-[10px] text-[#555]">Leave empty for auto-discovery</span>
              </label>
              <textarea
                v-model="editForm.mapping_config"
                @input="(e: any) => { editForm.mapping_config = e.target.value }"
                rows="12"
                placeholder='{"version": "1", "extractors": {...}}'
                class="w-full bg-[#0a0a0a] border border-white/10 rounded-xl px-3 py-2 text-[11px] text-[#ececec] font-mono focus:outline-none focus:border-violet-500/50 resize-none"
              />
              <p v-if="editForm.mapping_config && typeof editForm.mapping_config === 'string'" class="text-[10px] text-amber-400 mt-1">
                Warning: Invalid JSON will be ignored on save.
              </p>
            </div>
            <p v-if="editError" class="text-[12px] text-red-400 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">{{ editError }}</p>
          </div>
          <div class="px-6 py-4 bg-white/[0.02] border-t border-white/[0.06] flex justify-end gap-2 shrink-0">
            <button @click="showEditModal = false" class="px-4 py-2 text-[13px] text-[#7a7a7a] hover:text-white transition-colors">Cancel</button>
            <button
              @click="saveEdit"
              :disabled="isSaving"
              class="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-[13px] font-medium transition-colors disabled:opacity-40"
            >
              <svg v-if="isSaving" class="animate-spin inline mr-1" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Test Modal -->
    <Teleport to="body">
      <div v-if="showTestModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="showTestModal = false">
        <div class="bg-[#141414] border border-white/[0.1] rounded-2xl w-full max-w-4xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
          <div class="px-6 pt-5 pb-0 shrink-0">
            <h3 class="text-[16px] font-semibold text-white mb-1 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
              Test Mapping
            </h3>
            <p class="text-[12px] text-[#555] mb-4">{{ selectedWebhook?.name }}</p>
          </div>
          <div class="px-6 py-4 flex gap-4 flex-1 overflow-hidden">
            <!-- Left: Payload input -->
            <div class="flex-1 flex flex-col min-w-0">
              <label class="text-[12px] text-[#7a7a7a] mb-1 block">Payload JSON</label>
              <textarea
                v-model="testPayload"
                class="flex-1 bg-[#0a0a0a] border border-white/10 rounded-xl px-3 py-2 text-[11px] text-[#ececec] font-mono focus:outline-none focus:border-violet-500/50 resize-none"
                placeholder="Paste any JSON payload here..."
              />
              <div class="flex gap-2 mt-2">
                <button @click="testPayload = JSON.stringify({alert:{title:'Sobrepresion de Caldera',body:'PT-4401 reporta 327 PSI',priority:'critical',type:'sensor_alert',timestamp:new Date().toISOString()}},null,2)" class="px-2 py-1 rounded text-[10px] bg-white/5 hover:bg-white/10 border border-white/10 text-[#7a7a7a]">Boiler</button>
                <button @click="testPayload = JSON.stringify({metric:'coolant_flow_rate',current_value:42.3,baseline_avg:51.6,deviation_pct:-18.0,unit:'L/min'},null,2)" class="px-2 py-1 rounded text-[10px] bg-white/5 hover:bg-white/10 border border-white/10 text-[#7a7a7a]">Coolant</button>
                <button @click="testPayload = JSON.stringify({sensor_id:'VS-101',value:8.2,unit:'mm/s RMS',threshold_alert:7.1},null,2)" class="px-2 py-1 rounded text-[10px] bg-white/5 hover:bg-white/10 border border-white/10 text-[#7a7a7a]">Vibration</button>
                <button @click="testPayload = JSON.stringify({sensor_id:'TT-TR02',value:78,unit:'C',baseline_avg:70},null,2)" class="px-2 py-1 rounded text-[10px] bg-white/5 hover:bg-white/10 border border-white/10 text-[#7a7a7a]">Temp</button>
              </div>
            </div>
            <!-- Right: Results -->
            <div class="flex-1 flex flex-col min-w-0 bg-[#0a0a0a] border border-white/[0.06] rounded-xl overflow-hidden">
              <div class="px-3 py-2 bg-white/[0.02] border-b border-white/[0.06] flex items-center justify-between">
                <span class="text-[11px] font-bold text-[#7a7a7a] uppercase tracking-wider">Result</span>
                <button
                  @click="runTest"
                  :disabled="isTesting"
                  class="px-3 py-1 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-[11px] font-medium transition-colors disabled:opacity-40"
                >
                  <svg v-if="isTesting" class="animate-spin inline mr-1" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  Run Test
                </button>
              </div>
              <div class="flex-1 overflow-y-auto p-3">
                <div v-if="testError" class="text-[12px] text-red-400 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">{{ testError }}</div>
                <div v-else-if="testResult" class="space-y-3">
                  <div class="flex items-center gap-2">
                    <span class="text-[11px] text-[#7a7a7a]">Auto-discovered:</span>
                    <span class="text-[11px]" :class="testResult.auto_discovered ? 'text-purple-400' : 'text-[#555]'">{{ testResult.auto_discovered ? 'Yes' : 'No' }}</span>
                  </div>
                  <div class="bg-[#111] rounded-lg border border-white/[0.06] overflow-hidden">
                    <div class="px-3 py-1.5 bg-white/[0.02] border-b border-white/[0.06]">
                      <span class="text-[10px] font-bold text-[#7a7a7a] uppercase">Extracted Fields</span>
                    </div>
                    <div class="px-3 py-2 space-y-1">
                      <div v-for="(value, key) in testResult.extracted_fields" :key="key" class="flex justify-between text-[11px]">
                        <span class="text-[#7a7a7a]">{{ key }}</span>
                        <span class="text-[#ececec] font-mono truncate max-w-[200px]">{{ value ?? 'null' }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="bg-[#111] rounded-lg border border-white/[0.06] overflow-hidden">
                    <div class="px-3 py-1.5 bg-white/[0.02] border-b border-white/[0.06]">
                      <span class="text-[10px] font-bold text-[#7a7a7a] uppercase">Body Preview</span>
                    </div>
                    <pre class="px-3 py-2 text-[10px] text-[#888] font-mono overflow-x-auto">{{ JSON.stringify(testResult.body_preview, null, 2) }}</pre>
                  </div>
                </div>
                <div v-else class="flex flex-col items-center justify-center h-full text-[#555] text-[12px]">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mb-2"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
                  Click "Run Test" to see results
                </div>
              </div>
            </div>
          </div>
          <div class="px-6 py-4 bg-white/[0.02] border-t border-white/[0.06] flex justify-end shrink-0">
            <button @click="showTestModal = false" class="px-4 py-2 text-[13px] text-[#7a7a7a] hover:text-white transition-colors">Close</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
