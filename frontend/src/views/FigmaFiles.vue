<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'

const store = useAppStore()

const showAddModal = ref(false)
const newFileKey = ref('')
const newFileName = ref('')
const addError = ref('')

onMounted(() => {
  store.fetchWatchedFiles()
})

const addFile = async () => {
  addError.value = ''
  try {
    await store.addWatchedFile(newFileKey.value, newFileName.value)
    showAddModal.value = false
    newFileKey.value = ''
    newFileName.value = ''
  } catch (e: any) {
    addError.value = e.response?.data?.detail || 'Failed to add file'
  }
}

const removeFile = async (fileKey: string) => {
  if (confirm('Are you sure you want to stop watching this file?')) {
    await store.removeWatchedFile(fileKey)
  }
}

const generateDocs = async (fileKey: string) => {
  try {
    await store.generateDocumentation(fileKey)
  } catch (e) {
    console.error('Failed to generate docs:', e)
  }
}

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return 'Never'
  return new Date(dateStr).toLocaleString()
}
</script>

<template>
  <div class="p-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-3xl font-bold text-text-primary mb-2">Figma Files</h1>
        <p class="text-text-secondary">Manage watched Figma design files</p>
      </div>
      <button
        @click="showAddModal = true"
        class="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        Add File
      </button>
    </div>

    <!-- Files List -->
    <div v-if="store.watchedFiles.length === 0" class="bg-bg-secondary border border-border rounded-2xl p-12 text-center">
      <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-bg-tertiary flex items-center justify-center">
        <svg class="w-10 h-10 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      </div>
      <h3 class="text-xl font-semibold text-text-primary mb-2">No files being watched</h3>
      <p class="text-text-secondary mb-6">Add a Figma file to start generating documentation</p>
      <button
        @click="showAddModal = true"
        class="px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
      >
        Add Your First File
      </button>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="file in store.watchedFiles"
        :key="file.file_key"
        class="bg-bg-secondary border border-border rounded-2xl p-6 hover:border-border-hover transition-colors"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-2">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center">
                <svg class="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M5.5 3.21a3.29 3.29 0 1 0 0 6.58h3.29V3.21a3.29 3.29 0 0 0-3.29 0zm0 8.29a3.29 3.29 0 1 0 3.29 3.29V11.5H5.5zm8.29-8.29a3.29 3.29 0 0 0-3.29 3.29v3.29h3.29a3.29 3.29 0 0 0 0-6.58zm0 8.29h-3.29v3.29a3.29 3.29 0 1 0 3.29-3.29zm0 8.29a3.29 3.29 0 0 0-3.29-3.29h-3.29v3.29a3.29 3.29 0 0 0 6.58 0z"/>
                </svg>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-text-primary">{{ file.name }}</h3>
                <p class="text-sm text-text-muted font-mono">{{ file.file_key }}</p>
              </div>
            </div>

            <div class="grid grid-cols-3 gap-4 mt-4">
              <div>
                <p class="text-xs text-text-muted mb-1">Last Modified</p>
                <p class="text-sm text-text-secondary">{{ formatDate(file.last_modified) }}</p>
              </div>
              <div>
                <p class="text-xs text-text-muted mb-1">Last Checked</p>
                <p class="text-sm text-text-secondary">{{ formatDate(file.last_checked) }}</p>
              </div>
              <div>
                <p class="text-xs text-text-muted mb-1">Documentation</p>
                <span
                  class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium"
                  :class="file.doc_generated 
                    ? 'bg-green-500/20 text-green-400' 
                    : 'bg-yellow-500/20 text-yellow-400'"
                >
                  {{ file.doc_generated ? 'Generated' : 'Not Generated' }}
                </span>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 ml-4">
            <button
              @click="generateDocs(file.file_key)"
              class="p-3 bg-accent/20 hover:bg-accent/30 text-accent rounded-xl transition-colors"
              :disabled="store.isLoading"
              title="Generate Documentation"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </button>
            <button
              @click="removeFile(file.file_key)"
              class="p-3 bg-error/20 hover:bg-error/30 text-error rounded-xl transition-colors"
              title="Remove File"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add File Modal -->
    <Teleport to="body">
      <div
        v-if="showAddModal"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        @click.self="showAddModal = false"
      >
        <div class="bg-bg-secondary border border-border rounded-2xl p-6 w-full max-w-md animate-slide-up">
          <h2 class="text-xl font-semibold text-text-primary mb-4">Add Figma File</h2>
          
          <form @submit.prevent="addFile" class="space-y-4">
            <div>
              <label class="block text-sm text-text-secondary mb-2">File Key</label>
              <input
                v-model="newFileKey"
                type="text"
                placeholder="e.g., abc123xyz..."
                class="w-full bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
                required
              />
              <p class="text-xs text-text-muted mt-1">
                Find this in the Figma URL: figma.com/file/<strong>[file_key]</strong>/...
              </p>
            </div>

            <div>
              <label class="block text-sm text-text-secondary mb-2">Display Name</label>
              <input
                v-model="newFileName"
                type="text"
                placeholder="e.g., Main App Design"
                class="w-full bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
              />
            </div>

            <div v-if="addError" class="p-3 bg-error/20 border border-error/30 rounded-xl text-error text-sm">
              {{ addError }}
            </div>

            <div class="flex gap-3 pt-2">
              <button
                type="button"
                @click="showAddModal = false"
                class="flex-1 px-4 py-3 bg-bg-tertiary hover:bg-bg-elevated rounded-xl font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                class="flex-1 px-4 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors"
                :disabled="store.isLoading"
              >
                {{ store.isLoading ? 'Adding...' : 'Add File' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

