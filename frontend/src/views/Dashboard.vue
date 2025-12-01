<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useAppStore } from '@/stores/app'
import { RouterLink } from 'vue-router'

const store = useAppStore()

onMounted(async () => {
  await Promise.all([
    store.fetchStatus(),
    store.fetchWatchedFiles(),
    store.fetchDocumentation(),
  ])
})

const stats = computed(() => [
  {
    label: 'Watched Files',
    value: store.watchedFiles.length,
    icon: 'file',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    label: 'Documentation',
    value: store.documentation.length,
    icon: 'book',
    color: 'from-accent to-purple-500',
  },
  {
    label: 'Detection Status',
    value: store.isChangeDetectionRunning ? 'Active' : 'Inactive',
    icon: 'pulse',
    color: store.isChangeDetectionRunning ? 'from-green-500 to-emerald-500' : 'from-yellow-500 to-orange-500',
  },
])

const recentDocs = computed(() => store.documentation.slice(0, 5))
</script>

<template>
  <div class="p-8">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-text-primary mb-2">Dashboard</h1>
      <p class="text-text-secondary">Overview of your Figma documentation system</p>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="bg-bg-secondary border border-border rounded-2xl p-6 hover:border-border-hover transition-colors"
      >
        <div class="flex items-center justify-between mb-4">
          <div class="w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center" :class="stat.color">
            <svg v-if="stat.icon === 'file'" class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            <svg v-if="stat.icon === 'book'" class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <svg v-if="stat.icon === 'pulse'" class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
        </div>
        <p class="text-2xl font-bold text-text-primary mb-1">{{ stat.value }}</p>
        <p class="text-sm text-text-secondary">{{ stat.label }}</p>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <!-- Quick Actions Card -->
      <div class="bg-bg-secondary border border-border rounded-2xl p-6">
        <h2 class="text-xl font-semibold text-text-primary mb-4">Quick Actions</h2>
        <div class="space-y-3">
          <RouterLink
            to="/files"
            class="flex items-center gap-4 p-4 bg-bg-tertiary rounded-xl hover:bg-bg-elevated transition-colors"
          >
            <div class="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <svg class="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </div>
            <div>
              <p class="font-medium text-text-primary">Add Figma File</p>
              <p class="text-sm text-text-muted">Start tracking a new design file</p>
            </div>
          </RouterLink>

          <button
            @click="store.checkAllFiles"
            class="w-full flex items-center gap-4 p-4 bg-bg-tertiary rounded-xl hover:bg-bg-elevated transition-colors text-left"
            :disabled="store.isLoading"
          >
            <div class="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
              <svg class="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <div>
              <p class="font-medium text-text-primary">Check for Changes</p>
              <p class="text-sm text-text-muted">Manually scan all watched files</p>
            </div>
          </button>

          <RouterLink
            to="/analyze"
            class="flex items-center gap-4 p-4 bg-bg-tertiary rounded-xl hover:bg-bg-elevated transition-colors"
          >
            <div class="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <svg class="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div>
              <p class="font-medium text-text-primary">Analyze Code/App</p>
              <p class="text-sm text-text-muted">Generate docs from code or UI</p>
            </div>
          </RouterLink>
        </div>
      </div>

      <!-- Recent Documentation -->
      <div class="bg-bg-secondary border border-border rounded-2xl p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-xl font-semibold text-text-primary">Recent Documentation</h2>
          <RouterLink to="/docs" class="text-sm text-accent hover:text-accent-hover">View all</RouterLink>
        </div>
        
        <div v-if="recentDocs.length === 0" class="text-center py-8">
          <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-bg-tertiary flex items-center justify-center">
            <svg class="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p class="text-text-secondary">No documentation yet</p>
          <p class="text-sm text-text-muted mt-1">Add a Figma file to get started</p>
        </div>

        <div v-else class="space-y-3">
          <RouterLink
            v-for="doc in recentDocs"
            :key="doc.id"
            :to="`/docs/${doc.id}`"
            class="block p-4 bg-bg-tertiary rounded-xl hover:bg-bg-elevated transition-colors"
          >
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium text-text-primary">{{ doc.figma_file_name }}</p>
                <p class="text-sm text-text-muted">{{ doc.doc_type }} docs</p>
              </div>
              <span class="text-xs text-text-muted">
                {{ new Date(doc.created_at).toLocaleDateString() }}
              </span>
            </div>
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- System Status -->
    <div class="bg-bg-secondary border border-border rounded-2xl p-6">
      <h2 class="text-xl font-semibold text-text-primary mb-4">System Status</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="p-4 bg-bg-tertiary rounded-xl">
          <p class="text-sm text-text-muted mb-1">Ollama URL</p>
          <p class="font-mono text-sm text-text-secondary">
            {{ store.systemStatus?.config.ollama_url || 'Not connected' }}
          </p>
        </div>
        <div class="p-4 bg-bg-tertiary rounded-xl">
          <p class="text-sm text-text-muted mb-1">Default Model</p>
          <p class="font-mono text-sm text-text-secondary">
            {{ store.systemStatus?.config.default_model || 'Not set' }}
          </p>
        </div>
        <div class="p-4 bg-bg-tertiary rounded-xl">
          <p class="text-sm text-text-muted mb-1">Polling Interval</p>
          <p class="font-mono text-sm text-text-secondary">
            {{ store.systemStatus?.change_detection.polling_interval_minutes || '?' }} minutes
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

