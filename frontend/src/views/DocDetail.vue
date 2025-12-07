<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore, type Documentation } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const chatStore = useChatStore()

const doc = ref<Documentation | null>(null)
const isLoading = ref(true)
const isSplitView = ref(false)

onMounted(async () => {
  const docId = route.params.id as string
  doc.value = await store.getDocumentation(docId)
  isLoading.value = false
  
  // Set chat context to this file
  if (doc.value) {
    chatStore.setFileContext(doc.value.figma_file_key)
    if (doc.value.doc_type === 'both') {
      isSplitView.value = true
    }
  }
})

const splitContent = computed(() => {
  if (!doc.value?.content || !isSplitView.value) return null
  
  const content = doc.value.content
  let userMarkdown = ''
  let devMarkdown = ''
  
  // Split by Frame headers (### ...)
  // We look for ### lines. We treat everything before the first ### as preamble.
  const parts = content.split(/(?=^### )/m)
  
  parts.forEach(part => {
    // Check if this part has User/Dev split
    const userMatch = part.match(/^## User Perspective/m)
    const devMatch = part.match(/^## Developer Perspective/m)
    
    if (userMatch && devMatch) {
      // Both exist
      const userIdx = userMatch.index!
      const devIdx = devMatch.index!
      
      let common = ''
      let userPart = ''
      let devPart = ''
      
      if (userIdx < devIdx) {
        common = part.substring(0, userIdx)
        userPart = part.substring(userIdx, devIdx) // Include header? Yes
        devPart = part.substring(devIdx)
      } else {
        common = part.substring(0, devIdx)
        devPart = part.substring(devIdx, userIdx)
        userPart = part.substring(userIdx)
      }
      
      // Clean up headers if we want, but let's keep them for context
      // Actually, let's remove the specific "Perspective" headers to avoid clutter in split view,
      // but keep the content.
      // But keeping them is safer.
      
      userMarkdown += common + '\n' + userPart + '\n'
      devMarkdown += common + '\n' + devPart + '\n'
    } else {
      // No split found, add to both (or just user? let's add to both to be safe)
      userMarkdown += part
      devMarkdown += part
    }
  })
  
  return {
    user: DOMPurify.sanitize(marked(userMarkdown) as string),
    dev: DOMPurify.sanitize(marked(devMarkdown) as string)
  }
})

const renderedContent = computed(() => {
  if (!doc.value?.content) return ''
  const html = marked(doc.value.content) as string
  return DOMPurify.sanitize(html)
})

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const goBack = () => {
  router.push('/docs')
}

const regenerateDocs = async () => {
  if (!doc.value) return
  isLoading.value = true
  try {
    await store.generateDocumentation(doc.value.figma_file_key, doc.value.doc_type)
    doc.value = await store.getDocumentation(route.params.id as string)
  } catch (e) {
    console.error('Failed to regenerate:', e)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="p-8">
    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center justify-center py-20">
      <div class="w-12 h-12 border-4 border-accent/30 border-t-accent rounded-full animate-spin"></div>
    </div>

    <!-- Not Found -->
    <div v-else-if="!doc" class="text-center py-20">
      <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-bg-tertiary flex items-center justify-center">
        <svg class="w-10 h-10 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <h2 class="text-xl font-semibold text-text-primary mb-2">Documentation not found</h2>
      <p class="text-text-secondary mb-6">The requested documentation could not be found</p>
      <button
        @click="goBack"
        class="px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
      >
        Back to Documentation
      </button>
    </div>

    <!-- Content -->
    <div v-else>
      <!-- Header -->
      <div class="mb-8">
        <button
          @click="goBack"
          class="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors mb-4"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Documentation
        </button>

        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-3xl font-bold text-text-primary mb-2">{{ doc.figma_file_name }}</h1>
            <div class="flex items-center gap-4 text-sm text-text-muted">
              <span class="flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {{ formatDate(doc.created_at) }}
              </span>
              <span
                class="px-3 py-1 rounded-full text-xs font-medium bg-accent/20 text-accent"
              >
                {{ doc.doc_type }} docs
              </span>
              <span v-if="doc.figma_version" class="font-mono text-xs">
                v{{ doc.figma_version }}
              </span>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <button
              v-if="doc?.doc_type === 'both'"
              @click="isSplitView = !isSplitView"
              class="flex items-center gap-2 px-4 py-2 bg-bg-tertiary hover:bg-bg-elevated rounded-xl text-sm font-medium transition-colors"
              :class="{ 'bg-accent/20 text-accent': isSplitView }"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              {{ isSplitView ? 'Split View' : 'Combined View' }}
            </button>
            <button
              @click="regenerateDocs"
              class="flex items-center gap-2 px-4 py-2 bg-bg-tertiary hover:bg-bg-elevated rounded-xl text-sm font-medium transition-colors"
              :disabled="isLoading"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Regenerate
            </button>
          </div>
        </div>
      </div>

      <!-- Documentation Content -->
      <div v-if="splitContent" class="grid grid-cols-2 gap-6 h-[calc(100vh-200px)]">
        <!-- User Perspective -->
        <div class="bg-bg-secondary border border-border rounded-2xl flex flex-col min-h-0">
          <div class="p-4 border-b border-border bg-bg-tertiary rounded-t-2xl font-semibold text-text-primary sticky top-0">
            User Perspective
          </div>
          <div class="p-8 overflow-y-auto custom-scrollbar">
            <div class="markdown-content prose prose-invert max-w-none" v-html="splitContent.user"></div>
          </div>
        </div>
        
        <!-- Developer Perspective -->
        <div class="bg-bg-secondary border border-border rounded-2xl flex flex-col min-h-0">
          <div class="p-4 border-b border-border bg-bg-tertiary rounded-t-2xl font-semibold text-text-primary sticky top-0">
            Developer Perspective
          </div>
          <div class="p-8 overflow-y-auto custom-scrollbar">
            <div class="markdown-content prose prose-invert max-w-none" v-html="splitContent.dev"></div>
          </div>
        </div>
      </div>
      
      <div v-else class="bg-bg-secondary border border-border rounded-2xl p-8">
        <div class="markdown-content prose prose-invert max-w-none" v-html="renderedContent"></div>
      </div>
    </div>
  </div>
</template>

