<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore, type Documentation, type Screenshot } from '@/stores/app'
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
const selectedScreenshot = ref<Screenshot | null>(null)
const showLightbox = ref(false)
const zoomLevel = ref(1)

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

// Screenshot gallery functions
const getScreenshotUrl = (filename: string) => {
  return `/screenshots/${filename}`
}

const openLightbox = (screenshot: Screenshot) => {
  selectedScreenshot.value = screenshot
  showLightbox.value = true
}

const closeLightbox = () => {
  showLightbox.value = false
  selectedScreenshot.value = null
  zoomLevel.value = 1
}

const hasScreenshots = computed(() => {
  return doc.value?.screenshots && doc.value.screenshots.length > 0
})

// Simple zoom controls
const zoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value + 0.25, 3)
}

const zoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value - 0.25, 0.5)
}

const resetZoom = () => {
  zoomLevel.value = 1
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

      <!-- Screenshot Gallery -->
      <div v-if="hasScreenshots" class="mt-8">
        <h2 class="text-xl font-semibold text-text-primary mb-4 flex items-center gap-2">
          <svg class="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          Screenshots
          <span class="text-sm font-normal text-text-muted">({{ doc.screenshots?.length }} images)</span>
        </h2>

        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div
            v-for="(screenshot, index) in doc.screenshots"
            :key="index"
            class="group relative aspect-video bg-bg-tertiary rounded-xl overflow-hidden border border-border hover:border-accent/50 transition-all cursor-pointer"
            @click="openLightbox(screenshot)"
          >
            <img
              :src="getScreenshotUrl(screenshot.filename)"
              :alt="screenshot.title || 'Screenshot'"
              class="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-300"
            />
            <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
              <div class="absolute bottom-0 left-0 right-0 p-3">
                <p class="text-white text-sm font-medium truncate">{{ screenshot.title || 'Page Screenshot' }}</p>
                <p class="text-white/70 text-xs truncate">{{ screenshot.url }}</p>
              </div>
            </div>
            <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <div class="bg-black/50 backdrop-blur-sm rounded-lg p-2">
                <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Lightbox Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showLightbox && selectedScreenshot"
          class="fixed inset-0 z-50 bg-black/95 flex flex-col"
        >
          <!-- Top bar -->
          <div class="flex items-center justify-between p-4 bg-black/50">
            <!-- Info -->
            <div class="flex-1 min-w-0">
              <p class="text-white font-medium text-sm truncate">{{ selectedScreenshot.title || 'Page Screenshot' }}</p>
              <p class="text-white/60 text-xs truncate">{{ selectedScreenshot.url }}</p>
            </div>

            <!-- Zoom controls -->
            <div class="flex items-center gap-1 mx-4">
              <button @click="zoomOut" class="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors" title="Zoom out">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
                </svg>
              </button>
              <button @click="resetZoom" class="px-3 py-1 text-white/70 hover:text-white hover:bg-white/10 rounded-lg text-sm font-medium min-w-[60px] transition-colors">
                {{ Math.round(zoomLevel * 100) }}%
              </button>
              <button @click="zoomIn" class="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors" title="Zoom in">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>

            <!-- Close button -->
            <button
              @click="closeLightbox"
              class="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
            >
              <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Scrollable image container -->
          <div
            class="flex-1 overflow-auto p-4"
            @click.self="closeLightbox"
          >
            <div class="min-h-full flex items-center justify-center">
              <img
                :src="getScreenshotUrl(selectedScreenshot.filename)"
                :alt="selectedScreenshot.title || 'Screenshot'"
                class="transition-transform duration-200 ease-out"
                :style="{
                  transform: `scale(${zoomLevel})`,
                  transformOrigin: 'center center',
                }"
                draggable="false"
              />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
