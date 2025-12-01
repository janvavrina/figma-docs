<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { RouterLink } from 'vue-router'

const store = useAppStore()

onMounted(() => {
  store.fetchDocumentation()
})

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

const getDocTypeColor = (type: string) => {
  switch (type) {
    case 'user':
      return 'bg-blue-500/20 text-blue-400'
    case 'dev':
      return 'bg-green-500/20 text-green-400'
    default:
      return 'bg-purple-500/20 text-purple-400'
  }
}
</script>

<template>
  <div class="p-8">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-text-primary mb-2">Documentation</h1>
      <p class="text-text-secondary">Browse generated documentation from your Figma designs</p>
    </div>

    <!-- Empty State -->
    <div v-if="store.documentation.length === 0" class="bg-bg-secondary border border-border rounded-2xl p-12 text-center">
      <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-bg-tertiary flex items-center justify-center">
        <svg class="w-10 h-10 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      </div>
      <h3 class="text-xl font-semibold text-text-primary mb-2">No documentation yet</h3>
      <p class="text-text-secondary mb-6">Generate documentation from your Figma files to see them here</p>
      <RouterLink
        to="/files"
        class="inline-flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
        Go to Figma Files
      </RouterLink>
    </div>

    <!-- Documentation Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <RouterLink
        v-for="doc in store.documentation"
        :key="doc.id"
        :to="`/docs/${doc.id}`"
        class="bg-bg-secondary border border-border rounded-2xl p-6 hover:border-accent/50 transition-all duration-300 group"
      >
        <div class="flex items-start justify-between mb-4">
          <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-accent to-purple-500 flex items-center justify-center">
            <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <span
            class="px-3 py-1 rounded-full text-xs font-medium"
            :class="getDocTypeColor(doc.doc_type)"
          >
            {{ doc.doc_type }}
          </span>
        </div>

        <h3 class="text-lg font-semibold text-text-primary mb-2 group-hover:text-accent transition-colors">
          {{ doc.figma_file_name }}
        </h3>
        
        <p class="text-sm text-text-muted mb-4">
          {{ doc.title }}
        </p>

        <div class="flex items-center justify-between text-xs text-text-muted">
          <span>{{ formatDate(doc.created_at) }}</span>
          <span class="flex items-center gap-1">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
            View
          </span>
        </div>
      </RouterLink>
    </div>
  </div>
</template>

