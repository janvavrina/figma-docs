<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import axios from 'axios'

const store = useAppStore()
const api = axios.create({ baseURL: '/api' })

const config = ref<any>(null)
const isLoading = ref(true)

onMounted(async () => {
  await store.fetchStatus()
  try {
    const response = await api.get('/config')
    config.value = response.data
  } catch (e) {
    console.error('Failed to load config:', e)
  }
  isLoading.value = false
})

const toggleDetection = async () => {
  if (store.isChangeDetectionRunning) {
    await store.stopChangeDetection()
  } else {
    await store.startChangeDetection()
  }
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
        
        <div class="space-y-4">
          <div class="p-4 bg-bg-tertiary rounded-xl">
            <p class="text-sm text-text-muted mb-1">Ollama URL</p>
            <p class="font-mono text-sm text-text-primary">
              {{ config?.llm?.ollama_base_url || 'Not configured' }}
            </p>
          </div>

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

