<script setup lang="ts">
import { ref, computed } from 'vue'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

const activeTab = ref<'code' | 'app' | 'design'>('design')

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

// Design Check
const figmaFileKey = ref('')
const designAppUrl = ref('')
const designResult = ref<any>(null)
const designLoading = ref(false)
const designError = ref('')
const figmaFrames = ref<any[]>([])
const framesLoading = ref(false)
const frameMappings = ref<any[]>([])
const checkTypes = ref<string[]>(['visual', 'specs', 'elements'])

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

const loadFigmaFrames = async () => {
  if (!figmaFileKey.value) return
  
  framesLoading.value = true
  figmaFrames.value = []
  
  try {
    const response = await api.get(`/analyze/design-check/${figmaFileKey.value}/frames`)
    figmaFrames.value = response.data
    
    // Auto-populate mappings
    frameMappings.value = figmaFrames.value.slice(0, 5).map((frame: any) => ({
      figma_frame_id: frame.id,
      figma_frame_name: frame.name,
      app_url: designAppUrl.value || '',
    }))
  } catch (e: any) {
    designError.value = e.response?.data?.detail || 'Failed to load Figma frames'
  } finally {
    framesLoading.value = false
  }
}

const updateFrameUrl = (index: number, url: string) => {
  frameMappings.value[index].app_url = url
}

const removeFrameMapping = (index: number) => {
  frameMappings.value.splice(index, 1)
}

const addFrameMapping = (frame: any) => {
  if (!frameMappings.value.find(m => m.figma_frame_id === frame.id)) {
    frameMappings.value.push({
      figma_frame_id: frame.id,
      figma_frame_name: frame.name,
      app_url: designAppUrl.value || '',
    })
  }
}

const runDesignCheck = async () => {
  if (!figmaFileKey.value || !designAppUrl.value) return
  
  designLoading.value = true
  designError.value = ''
  designResult.value = null
  
  try {
    const response = await api.post('/analyze/design-check', {
      figma_file_key: figmaFileKey.value,
      app_url: designAppUrl.value,
      frame_mappings: frameMappings.value.length > 0 ? frameMappings.value : null,
      check_types: checkTypes.value,
    })
    designResult.value = response.data
  } catch (e: any) {
    designError.value = e.response?.data?.detail || 'Failed to run design check'
  } finally {
    designLoading.value = false
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'pass': return 'text-green-400 bg-green-500/20'
    case 'fail': return 'text-red-400 bg-red-500/20'
    case 'warning': return 'text-yellow-400 bg-yellow-500/20'
    default: return 'text-gray-400 bg-gray-500/20'
  }
}

const getScoreColor = (score: number) => {
  if (score >= 90) return 'text-green-400'
  if (score >= 70) return 'text-yellow-400'
  return 'text-red-400'
}
</script>

<template>
  <div class="p-8">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-text-primary mb-2">Analyze</h1>
      <p class="text-text-secondary">Generate documentation from code, app UI, or compare designs</p>
    </div>

    <!-- Tabs -->
    <div class="flex gap-2 mb-6">
      <button
        @click="activeTab = 'design'"
        class="px-6 py-3 rounded-xl font-medium transition-all"
        :class="activeTab === 'design' 
          ? 'bg-accent text-white' 
          : 'bg-bg-secondary text-text-secondary hover:text-text-primary'"
      >
        <span class="flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Design Check
        </span>
      </button>
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

    <!-- Design Check Panel -->
    <div v-if="activeTab === 'design'" class="space-y-6">
      <div class="bg-bg-secondary border border-border rounded-2xl p-6">
        <h2 class="text-xl font-semibold text-text-primary mb-4">Design vs Implementation Check</h2>
        <p class="text-text-secondary mb-6">
          Compare your Figma designs with the actual running application. 
          Detect visual mismatches, style differences, and missing elements.
        </p>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <!-- Figma File -->
          <div>
            <label class="block text-sm text-text-secondary mb-2">Figma File Key</label>
            <div class="flex gap-2">
              <input
                v-model="figmaFileKey"
                type="text"
                placeholder="e.g., abc123xyz..."
                class="flex-1 bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
              />
              <button
                @click="loadFigmaFrames"
                :disabled="!figmaFileKey || framesLoading"
                class="px-4 py-3 bg-bg-tertiary hover:bg-bg-elevated border border-border rounded-xl transition-colors disabled:opacity-50"
              >
                {{ framesLoading ? '...' : 'Load' }}
              </button>
            </div>
            <p class="text-xs text-text-muted mt-1">
              Find this in the Figma URL: figma.com/file/<strong>[file_key]</strong>/...
            </p>
          </div>

          <!-- App URL -->
          <div>
            <label class="block text-sm text-text-secondary mb-2">Application URL</label>
            <input
              v-model="designAppUrl"
              type="url"
              placeholder="http://localhost:3000"
              class="w-full bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
            />
            <p class="text-xs text-text-muted mt-1">
              The URL of your running application to compare against
            </p>
          </div>
        </div>

        <!-- Check Types -->
        <div class="mt-6">
          <label class="block text-sm text-text-secondary mb-2">Check Types</label>
          <div class="flex flex-wrap gap-3">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                value="visual"
                v-model="checkTypes"
                class="w-4 h-4 rounded border-border bg-bg-tertiary text-accent focus:ring-accent"
              />
              <span class="text-text-primary">Visual (Screenshot Diff)</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                value="specs"
                v-model="checkTypes"
                class="w-4 h-4 rounded border-border bg-bg-tertiary text-accent focus:ring-accent"
              />
              <span class="text-text-primary">Specifications (Colors, Fonts)</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                value="elements"
                v-model="checkTypes"
                class="w-4 h-4 rounded border-border bg-bg-tertiary text-accent focus:ring-accent"
              />
              <span class="text-text-primary">Elements (Buttons, Inputs)</span>
            </label>
          </div>
        </div>

        <!-- Frame Mappings -->
        <div v-if="figmaFrames.length > 0" class="mt-6">
          <label class="block text-sm text-text-secondary mb-2">Frame Mappings ({{ frameMappings.length }} selected)</label>
          
          <!-- Available Frames -->
          <div class="mb-4">
            <p class="text-xs text-text-muted mb-2">Available Figma frames:</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="frame in figmaFrames"
                :key="frame.id"
                @click="addFrameMapping(frame)"
                :disabled="frameMappings.find(m => m.figma_frame_id === frame.id)"
                class="px-3 py-1 text-sm bg-bg-tertiary hover:bg-bg-elevated rounded-lg transition-colors disabled:opacity-50"
              >
                {{ frame.name }}
              </button>
            </div>
          </div>

          <!-- Selected Mappings -->
          <div class="space-y-2">
            <div
              v-for="(mapping, index) in frameMappings"
              :key="mapping.figma_frame_id"
              class="flex items-center gap-3 p-3 bg-bg-tertiary rounded-xl"
            >
              <span class="text-sm text-text-primary font-medium min-w-[150px]">
                {{ mapping.figma_frame_name }}
              </span>
              <span class="text-text-muted">→</span>
              <input
                :value="mapping.app_url"
                @input="updateFrameUrl(index, ($event.target as HTMLInputElement).value)"
                type="url"
                placeholder="App page URL"
                class="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
              />
              <button
                @click="removeFrameMapping(index)"
                class="p-2 text-text-muted hover:text-error transition-colors"
              >
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Run Button -->
        <div class="mt-6">
          <button
            @click="runDesignCheck"
            class="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
            :disabled="designLoading || !figmaFileKey || !designAppUrl"
          >
            <svg v-if="designLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {{ designLoading ? 'Running Check...' : 'Run Design Check' }}
          </button>
        </div>

        <div v-if="designError" class="mt-4 p-4 bg-error/20 border border-error/30 rounded-xl text-error">
          {{ designError }}
        </div>
      </div>

      <!-- Results -->
      <div v-if="designResult" class="bg-bg-secondary border border-border rounded-2xl p-6">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-xl font-semibold text-text-primary">Design Check Results</h2>
          <div class="flex items-center gap-4">
            <div class="text-center">
              <div class="text-3xl font-bold" :class="getScoreColor(designResult.overall_score)">
                {{ designResult.overall_score }}%
              </div>
              <div class="text-xs text-text-muted">Match Score</div>
            </div>
          </div>
        </div>

        <!-- Summary -->
        <div class="grid grid-cols-4 gap-4 mb-6">
          <div class="bg-bg-tertiary rounded-xl p-4 text-center">
            <div class="text-2xl font-bold text-text-primary">{{ designResult.summary.total_checks }}</div>
            <div class="text-xs text-text-muted">Total Checks</div>
          </div>
          <div class="bg-green-500/10 rounded-xl p-4 text-center">
            <div class="text-2xl font-bold text-green-400">{{ designResult.summary.passed }}</div>
            <div class="text-xs text-text-muted">Passed</div>
          </div>
          <div class="bg-red-500/10 rounded-xl p-4 text-center">
            <div class="text-2xl font-bold text-red-400">{{ designResult.summary.failed }}</div>
            <div class="text-xs text-text-muted">Failed</div>
          </div>
          <div class="bg-yellow-500/10 rounded-xl p-4 text-center">
            <div class="text-2xl font-bold text-yellow-400">{{ designResult.summary.warnings }}</div>
            <div class="text-xs text-text-muted">Warnings</div>
          </div>
        </div>

        <!-- Comparisons -->
        <div class="space-y-4">
          <h3 class="text-lg font-semibold text-text-primary">Detailed Results</h3>
          
          <div
            v-for="comparison in designResult.comparisons"
            :key="comparison.figma_frame_id"
            class="bg-bg-tertiary rounded-xl p-4"
          >
            <div class="flex items-center justify-between mb-3">
              <div>
                <h4 class="font-medium text-text-primary">{{ comparison.figma_frame }}</h4>
                <p class="text-sm text-text-muted">{{ comparison.app_url }}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-sm text-green-400">{{ comparison.passed }} passed</span>
                <span v-if="comparison.failed > 0" class="text-sm text-red-400">{{ comparison.failed }} failed</span>
                <span v-if="comparison.warnings > 0" class="text-sm text-yellow-400">{{ comparison.warnings }} warnings</span>
              </div>
            </div>

            <div class="space-y-2">
              <div
                v-for="(check, idx) in comparison.checks"
                :key="idx"
                class="flex items-center gap-3 p-2 bg-bg-secondary rounded-lg"
              >
                <span
                  class="px-2 py-1 text-xs font-medium rounded"
                  :class="getStatusColor(check.status)"
                >
                  {{ check.status.toUpperCase() }}
                </span>
                <span class="text-sm text-text-muted">{{ check.check_type }}</span>
                <span class="text-sm text-text-secondary flex-1">{{ check.message }}</span>
                <span v-if="check.similarity_percent" class="text-sm font-mono text-text-muted">
                  {{ check.similarity_percent }}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- LLM Analysis -->
        <div v-if="designResult.analysis" class="mt-6">
          <h3 class="text-lg font-semibold text-text-primary mb-3">AI Analysis</h3>
          <div class="bg-bg-tertiary rounded-xl p-4">
            <pre class="text-sm text-text-secondary whitespace-pre-wrap">{{ designResult.analysis }}</pre>
          </div>
        </div>
      </div>
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
