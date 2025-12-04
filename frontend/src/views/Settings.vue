<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import axios from 'axios'

const store = useAppStore()
const api = axios.create({ baseURL: '/api' })

const config = ref<any>(null)
const ollamaStatus = ref<any>(null)
const availableModels = ref<any[]>([])
const isLoading = ref(true)
const isPulling = ref(false)
const pullStatus = ref('')
const pullModelName = ref('')
const ensureStatus = ref<any>(null)

onMounted(async () => {
  await store.fetchStatus()
  await loadData()
  isLoading.value = false
})

const loadData = async () => {
  try {
    const [configRes, statusRes, modelsRes] = await Promise.all([
      api.get('/config'),
      api.get('/ollama/status'),
      api.get('/ollama/models').catch(() => ({ data: { models: [] } })),
    ])
    config.value = configRes.data
    ollamaStatus.value = statusRes.data
    availableModels.value = modelsRes.data.models || []
  } catch (e) {
    console.error('Failed to load data:', e)
  }
}

const toggleDetection = async () => {
  if (store.isChangeDetectionRunning) {
    await store.stopChangeDetection()
  } else {
    await store.startChangeDetection()
  }
}

const pullModel = async () => {
  if (!pullModelName.value.trim() || isPulling.value) return
  
  isPulling.value = true
  pullStatus.value = `Pulling ${pullModelName.value}...`
  
  try {
    const response = await api.post('/ollama/models/pull', {
      model_name: pullModelName.value,
    })
    pullStatus.value = response.data.message
    pullModelName.value = ''
    // Refresh models list
    await loadData()
  } catch (e: any) {
    pullStatus.value = `Error: ${e.response?.data?.detail || e.message}`
  } finally {
    isPulling.value = false
  }
}

const ensureModels = async () => {
  isPulling.value = true
  pullStatus.value = 'Ensuring all required models are available...'
  ensureStatus.value = null
  
  try {
    const response = await api.post('/ollama/models/ensure')
    ensureStatus.value = response.data
    pullStatus.value = 'Model check complete!'
    await loadData()
  } catch (e: any) {
    pullStatus.value = `Error: ${e.response?.data?.detail || e.message}`
  } finally {
    isPulling.value = false
  }
}

const formatSize = (bytes: number) => {
  if (!bytes) return 'Unknown'
  const gb = bytes / (1024 * 1024 * 1024)
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(0)} MB`
}
</script>

<template>
  <div class="p-8">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-text-primary mb-2">Settings</h1>
      <p class="text-text-secondary">Configure your Figma Documentation Generator</p>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center justify-center py-20">
      <div class="w-12 h-12 border-4 border-accent/30 border-t-accent rounded-full animate-spin"></div>
    </div>

    <div v-else class="space-y-6">
      <!-- Ollama Status -->
      <div class="bg-bg-secondary border border-border rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h2 class="text-xl font-semibold text-text-primary">Ollama Server</h2>
            <p class="text-sm text-text-secondary mt-1">
              External LLM server status and model management
            </p>
          </div>
          <div class="flex items-center gap-2">
            <div 
              class="w-3 h-3 rounded-full"
              :class="ollamaStatus?.status === 'online' ? 'bg-success' : 'bg-error'"
            ></div>
            <span class="text-sm font-medium" :class="ollamaStatus?.status === 'online' ? 'text-success' : 'text-error'">
              {{ ollamaStatus?.status === 'online' ? 'Online' : 'Offline' }}
            </span>
          </div>
        </div>

        <div class="grid grid-cols-3 gap-4 mb-4">
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">URL</p>
            <p class="font-mono text-sm text-text-primary truncate">
              {{ ollamaStatus?.url || 'Not configured' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Connection Type</p>
            <p class="font-mono text-sm text-text-primary">
              {{ ollamaStatus?.is_ngrok ? 'ngrok tunnel' : 'Direct' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Available Models</p>
            <p class="font-mono text-sm text-text-primary">
              {{ ollamaStatus?.models_count || 0 }}
            </p>
          </div>
        </div>

        <!-- Available Models List -->
        <div v-if="availableModels.length > 0" class="mb-4">
          <p class="text-sm text-text-muted mb-2">Installed Models:</p>
          <div class="flex flex-wrap gap-2">
            <span 
              v-for="model in availableModels" 
              :key="model.name"
              class="px-3 py-1 bg-bg-tertiary rounded-lg text-sm font-mono text-text-secondary"
            >
              {{ model.name }}
              <span class="text-text-muted text-xs ml-1">({{ formatSize(model.size) }})</span>
            </span>
          </div>
        </div>

        <!-- Pull Model -->
        <div class="border-t border-border pt-4 mt-4">
          <p class="text-sm text-text-muted mb-3">Pull a new model:</p>
          <div class="flex gap-3">
            <input
              v-model="pullModelName"
              type="text"
              placeholder="e.g., gemma3:27b, llama3.2:3b"
              class="flex-1 bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
              :disabled="isPulling"
            />
            <button
              @click="pullModel"
              class="px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors disabled:opacity-50"
              :disabled="isPulling || !pullModelName.trim()"
            >
              {{ isPulling ? 'Pulling...' : 'Pull Model' }}
            </button>
          </div>
          
          <div class="mt-3 flex gap-3">
            <button
              @click="ensureModels"
              class="px-4 py-2 bg-bg-tertiary hover:bg-bg-elevated rounded-xl text-sm font-medium transition-colors disabled:opacity-50"
              :disabled="isPulling"
            >
              Ensure All Required Models
            </button>
            <button
              @click="loadData"
              class="px-4 py-2 bg-bg-tertiary hover:bg-bg-elevated rounded-xl text-sm font-medium transition-colors"
            >
              Refresh
            </button>
          </div>

          <p v-if="pullStatus" class="mt-3 text-sm" :class="pullStatus.includes('Error') ? 'text-error' : 'text-success'">
            {{ pullStatus }}
          </p>

          <!-- Ensure Status -->
          <div v-if="ensureStatus" class="mt-4 p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm font-medium text-text-primary mb-2">Model Check Results:</p>
            <div class="space-y-1 text-sm">
              <p v-if="ensureStatus.already_available?.length" class="text-success">
                ✓ Already available: {{ ensureStatus.already_available.join(', ') }}
              </p>
              <p v-if="ensureStatus.pulled?.length" class="text-accent">
                ↓ Pulled: {{ ensureStatus.pulled.join(', ') }}
              </p>
              <p v-if="ensureStatus.failed?.length" class="text-error">
                ✗ Failed: {{ ensureStatus.failed.map((f: any) => f.model).join(', ') }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Change Detection -->
      <div class="bg-bg-secondary border border-border rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h2 class="text-xl font-semibold text-text-primary">Change Detection</h2>
            <p class="text-sm text-text-secondary mt-1">
              Automatically detect changes in watched Figma files
            </p>
          </div>
          <button
            @click="toggleDetection"
            class="relative w-14 h-8 rounded-full transition-colors"
            :class="store.isChangeDetectionRunning ? 'bg-accent' : 'bg-bg-tertiary'"
          >
            <div
              class="absolute top-1 w-6 h-6 bg-white rounded-full transition-transform"
              :class="store.isChangeDetectionRunning ? 'translate-x-7' : 'translate-x-1'"
            ></div>
          </button>
        </div>

        <div class="grid grid-cols-2 gap-4 mt-4">
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Status</p>
            <p class="font-medium" :class="store.isChangeDetectionRunning ? 'text-success' : 'text-warning'">
              {{ store.isChangeDetectionRunning ? 'Active' : 'Inactive' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Polling Interval</p>
            <p class="font-medium text-text-primary">
              {{ store.systemStatus?.change_detection.polling_interval_minutes || '?' }} minutes
            </p>
          </div>
        </div>
      </div>

      <!-- LLM Configuration -->
      <div class="bg-bg-secondary border border-border rounded-2xl p-6">
        <h2 class="text-xl font-semibold text-text-primary mb-4">LLM Configuration</h2>
        
        <div class="grid grid-cols-2 gap-4">
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Documentation Model</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.llm?.models?.documentation || 'Not set' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Chatbot Model</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.llm?.models?.chatbot || 'Not set' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Code Analysis Model</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.llm?.models?.code_analysis || 'Not set' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">App Analysis Model</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.llm?.models?.app_analysis || 'Not set' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Documentation Settings -->
      <div class="bg-bg-secondary border border-border rounded-2xl p-6">
        <h2 class="text-xl font-semibold text-text-primary mb-4">Documentation Settings</h2>
        
        <div class="grid grid-cols-3 gap-4">
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Output Directory</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.documentation?.output_dir || './docs' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Default Type</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.documentation?.default_type || 'both' }}
            </p>
          </div>
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Output Formats</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.documentation?.formats?.join(', ') || 'markdown, html' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Config File Notice -->
      <div class="bg-bg-tertiary border border-border rounded-2xl p-6">
        <div class="flex items-start gap-4">
          <div class="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center flex-shrink-0">
            <svg class="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h3 class="font-medium text-text-primary mb-1">Configuration File</h3>
            <p class="text-sm text-text-secondary">
              To change these settings, edit the <code class="bg-bg-secondary px-2 py-1 rounded text-accent">config.yaml</code> file 
              in the project root directory and restart the server.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
