<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

const activeTab = ref<'code' | 'app'>('code')

// Code Analysis
const projectPath = ref('')
const codeResult = ref<any>(null)
const codeLoading = ref(false)
const codeError = ref('')

// App Analysis
const appUrl = ref('')
const appResult = ref<any>(null)
const appLoading = ref(false)
const appError = ref('')

const analyzeCode = async () => {
  if (!projectPath.value) return
  
  codeLoading.value = true
  codeError.value = ''
  codeResult.value = null
  
  try {
    const response = await api.post('/analyze/code', {
      project_path: projectPath.value,
    })
    codeResult.value = response.data
  } catch (e: any) {
    codeError.value = e.response?.data?.detail || 'Failed to analyze code'
  } finally {
    codeLoading.value = false
  }
}

const analyzeApp = async () => {
  if (!appUrl.value) return
  
  appLoading.value = true
  appError.value = ''
  appResult.value = null
  
  try {
    const response = await api.post('/analyze/app', {
      app_url: appUrl.value,
    })
    appResult.value = response.data
  } catch (e: any) {
    appError.value = e.response?.data?.detail || 'Failed to analyze app'
  } finally {
    appLoading.value = false
  }
}
</script>

<template>
  <div class="p-8">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-text-primary mb-2">Analyze</h1>
      <p class="text-text-secondary">Generate documentation from code or application UI</p>
    </div>

    <!-- Tabs -->
    <div class="flex gap-2 mb-6">
      <button
        @click="activeTab = 'code'"
        class="px-6 py-3 rounded-xl font-medium transition-all"
        :class="activeTab === 'code' 
          ? 'bg-accent text-white' 
          : 'bg-bg-secondary text-text-secondary hover:text-text-primary'"
      >
        <span class="flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          Code Analysis
        </span>
      </button>
      <button
        @click="activeTab = 'app'"
        class="px-6 py-3 rounded-xl font-medium transition-all"
        :class="activeTab === 'app' 
          ? 'bg-accent text-white' 
          : 'bg-bg-secondary text-text-secondary hover:text-text-primary'"
      >
        <span class="flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          App Analysis
        </span>
      </button>
    </div>

    <!-- Code Analysis Panel -->
    <div v-if="activeTab === 'code'" class="bg-bg-secondary border border-border rounded-2xl p-6">
      <h2 class="text-xl font-semibold text-text-primary mb-4">Code Analysis</h2>
      <p class="text-text-secondary mb-6">
        Analyze your project's source code to generate technical documentation.
        The agent will scan files, understand the structure, and create comprehensive docs.
      </p>

      <div class="space-y-4">
        <div>
          <label class="block text-sm text-text-secondary mb-2">Project Path</label>
          <input
            v-model="projectPath"
            type="text"
            placeholder="/path/to/your/project"
            class="w-full bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
          />
          <p class="text-xs text-text-muted mt-1">
            Enter the absolute path to the project directory you want to analyze
          </p>
        </div>

        <button
          @click="analyzeCode"
          class="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
          :disabled="codeLoading || !projectPath"
        >
          <svg v-if="codeLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          {{ codeLoading ? 'Analyzing...' : 'Analyze Code' }}
        </button>

        <div v-if="codeError" class="p-4 bg-error/20 border border-error/30 rounded-xl text-error">
          {{ codeError }}
        </div>

        <div v-if="codeResult" class="mt-6 p-4 bg-bg-tertiary rounded-xl">
          <h3 class="font-semibold text-text-primary mb-2">Analysis Complete</h3>
          <pre class="text-sm text-text-secondary overflow-auto">{{ JSON.stringify(codeResult, null, 2) }}</pre>
        </div>
      </div>
    </div>

    <!-- App Analysis Panel -->
    <div v-if="activeTab === 'app'" class="bg-bg-secondary border border-border rounded-2xl p-6">
      <h2 class="text-xl font-semibold text-text-primary mb-4">App Analysis</h2>
      <p class="text-text-secondary mb-6">
        Analyze a running application's UI to generate user documentation.
        The agent will navigate through the app, take screenshots, and describe the interface.
      </p>

      <div class="space-y-4">
        <div>
          <label class="block text-sm text-text-secondary mb-2">Application URL</label>
          <input
            v-model="appUrl"
            type="url"
            placeholder="http://localhost:3000"
            class="w-full bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
          />
          <p class="text-xs text-text-muted mt-1">
            Enter the URL of the running application you want to analyze
          </p>
        </div>

        <button
          @click="analyzeApp"
          class="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
          :disabled="appLoading || !appUrl"
        >
          <svg v-if="appLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          {{ appLoading ? 'Analyzing...' : 'Analyze App' }}
        </button>

        <div v-if="appError" class="p-4 bg-error/20 border border-error/30 rounded-xl text-error">
          {{ appError }}
        </div>

        <div v-if="appResult" class="mt-6 p-4 bg-bg-tertiary rounded-xl">
          <h3 class="font-semibold text-text-primary mb-2">Analysis Complete</h3>
          <pre class="text-sm text-text-secondary overflow-auto">{{ JSON.stringify(appResult, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

