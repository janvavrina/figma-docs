<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import axios from 'axios'

const store = useAppStore()
const api = axios.create({ baseURL: '/api' })

// Browser state
const teamId = ref(localStorage.getItem('figma_team_id') || '')
const projects = ref<any[]>([])
const selectedProject = ref<any>(null)
const projectFiles = ref<any[]>([])
const isLoadingProjects = ref(false)
const isLoadingFiles = ref(false)
const browserError = ref('')
const figmaUser = ref<any>(null)
const isVerifyingToken = ref(false)

// Modal state
const showAddModal = ref(false)
const newFileKey = ref('')
const newFileName = ref('')
const addError = ref('')

onMounted(async () => {
  store.fetchWatchedFiles()
  await verifyFigmaToken()
  if (teamId.value && figmaUser.value) {
    loadProjects()
  }
})

// Save team ID to localStorage
watch(teamId, (val) => {
  localStorage.setItem('figma_team_id', val)
})

const verifyFigmaToken = async () => {
  isVerifyingToken.value = true
  try {
    const response = await api.get('/figma/me')
    figmaUser.value = response.data
    console.log('Figma user:', figmaUser.value)
  } catch (e: any) {
    console.error('Figma token verification failed:', e)
    figmaUser.value = null
    browserError.value = 'Figma API token is invalid or not set. Check your FIGMA_API_TOKEN environment variable.'
  } finally {
    isVerifyingToken.value = false
  }
}

const loadProjects = async () => {
  if (!teamId.value.trim()) {
    browserError.value = 'Please enter a Team ID'
    return
  }
  
  if (!figmaUser.value) {
    browserError.value = 'Figma API token is not valid. Please check your configuration.'
    return
  }
  
  isLoadingProjects.value = true
  browserError.value = ''
  projects.value = []
  selectedProject.value = null
  projectFiles.value = []
  
  try {
    console.log('Loading projects for team:', teamId.value)
    const response = await api.get(`/figma/teams/${teamId.value}/projects`)
    console.log('Projects response:', response.data)
    projects.value = response.data
    if (projects.value.length === 0) {
      browserError.value = 'No projects found in this team. Make sure you have access to at least one project.'
    }
  } catch (e: any) {
    console.error('Error loading projects:', e.response || e)
    browserError.value = e.response?.data?.detail || 'Failed to load projects. Check your Team ID and API token.'
  } finally {
    isLoadingProjects.value = false
  }
}

const selectProject = async (project: any) => {
  selectedProject.value = project
  isLoadingFiles.value = true
  projectFiles.value = []
  browserError.value = ''
  
  try {
    const response = await api.get(`/figma/projects/${project.id}/files`)
    projectFiles.value = response.data
  } catch (e: any) {
    browserError.value = e.response?.data?.detail || 'Failed to load files'
  } finally {
    isLoadingFiles.value = false
  }
}

const addFileFromBrowser = async (file: any) => {
  try {
    await store.addWatchedFile(file.key, file.name)
  } catch (e: any) {
    browserError.value = e.response?.data?.detail || 'Failed to add file'
  }
}

const isFileWatched = (fileKey: string) => {
  return store.watchedFiles.some(f => f.file_key === fileKey)
}

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
        <p class="text-text-secondary">Browse and manage Figma design files</p>
      </div>
      <div class="flex items-center gap-4">
        <!-- Figma Connection Status -->
        <div v-if="isVerifyingToken" class="flex items-center gap-2 text-sm text-text-muted">
          <div class="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin"></div>
          Connecting...
        </div>
        <div v-else-if="figmaUser" class="flex items-center gap-2 px-3 py-1.5 bg-green-500/20 rounded-lg">
          <div class="w-2 h-2 rounded-full bg-green-500"></div>
          <span class="text-sm text-green-400">{{ figmaUser.handle || figmaUser.email }}</span>
        </div>
        <div v-else class="flex items-center gap-2 px-3 py-1.5 bg-error/20 rounded-lg">
          <div class="w-2 h-2 rounded-full bg-error"></div>
          <span class="text-sm text-error">Not connected</span>
        </div>
        
        <button
          @click="showAddModal = true"
          class="flex items-center gap-2 px-4 py-2 bg-bg-tertiary hover:bg-bg-elevated rounded-xl font-medium transition-colors text-sm"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Add by Key
        </button>
      </div>
    </div>

    <!-- File Browser -->
    <div class="bg-bg-secondary border border-border rounded-2xl p-6 mb-8">
      <h2 class="text-lg font-semibold text-text-primary mb-4">Browse Figma Team</h2>
      
      <!-- Team ID Input -->
      <div class="flex gap-3 mb-4">
        <input
          v-model="teamId"
          type="text"
          placeholder="Enter your Figma Team ID..."
          class="flex-1 bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
          @keyup.enter="loadProjects"
        />
        <button
          @click="loadProjects"
          :disabled="isLoadingProjects || !teamId.trim()"
          class="px-6 py-3 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-colors disabled:opacity-50"
        >
          {{ isLoadingProjects ? 'Loading...' : 'Load Projects' }}
        </button>
      </div>
      
      <p class="text-xs text-text-muted mb-4">
        Find your Team ID in Figma: Team page URL → figma.com/files/team/<strong>[team_id]</strong>/...
      </p>

      <!-- Error -->
      <div v-if="browserError" class="p-3 bg-error/20 border border-error/30 rounded-xl text-error text-sm mb-4">
        {{ browserError }}
      </div>

      <!-- Projects & Files Grid -->
      <div v-if="projects.length > 0" class="grid grid-cols-2 gap-4">
        <!-- Projects List -->
        <div class="bg-bg-tertiary rounded-xl p-4">
          <h3 class="text-sm font-medium text-text-secondary mb-3">Projects</h3>
          <div class="space-y-2 max-h-80 overflow-y-auto">
            <button
              v-for="project in projects"
              :key="project.id"
              @click="selectProject(project)"
              class="w-full text-left px-4 py-3 rounded-lg transition-colors"
              :class="selectedProject?.id === project.id 
                ? 'bg-accent/20 text-accent border border-accent/30' 
                : 'bg-bg-secondary hover:bg-bg-elevated text-text-primary'"
            >
              <div class="flex items-center gap-3">
                <svg class="w-5 h-5 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                <span class="truncate">{{ project.name }}</span>
              </div>
            </button>
          </div>
        </div>

        <!-- Files List -->
        <div class="bg-bg-tertiary rounded-xl p-4">
          <h3 class="text-sm font-medium text-text-secondary mb-3">
            {{ selectedProject ? `Files in "${selectedProject.name}"` : 'Select a project' }}
          </h3>
          
          <div v-if="isLoadingFiles" class="flex items-center justify-center py-8">
            <div class="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin"></div>
          </div>
          
          <div v-else-if="projectFiles.length > 0" class="space-y-2 max-h-80 overflow-y-auto">
            <div
              v-for="file in projectFiles"
              :key="file.key"
              class="flex items-center gap-3 px-4 py-3 bg-bg-secondary rounded-lg"
            >
              <!-- Thumbnail -->
              <img 
                v-if="file.thumbnail_url" 
                :src="file.thumbnail_url" 
                class="w-10 h-10 rounded object-cover flex-shrink-0"
                alt=""
              />
              <div v-else class="w-10 h-10 rounded bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center flex-shrink-0">
                <svg class="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M5.5 3.21a3.29 3.29 0 1 0 0 6.58h3.29V3.21a3.29 3.29 0 0 0-3.29 0zm0 8.29a3.29 3.29 0 1 0 3.29 3.29V11.5H5.5z"/>
                </svg>
              </div>
              
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-text-primary truncate">{{ file.name }}</p>
                <p class="text-xs text-text-muted font-mono truncate">{{ file.key }}</p>
              </div>
              
              <button
                v-if="!isFileWatched(file.key)"
                @click="addFileFromBrowser(file)"
                class="p-2 bg-accent/20 hover:bg-accent/30 text-accent rounded-lg transition-colors flex-shrink-0"
                title="Add to watch list"
              >
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </button>
              <span
                v-else
                class="px-2 py-1 bg-green-500/20 text-green-400 rounded-lg text-xs font-medium flex-shrink-0"
              >
                Watching
              </span>
            </div>
          </div>
          
          <div v-else-if="selectedProject" class="text-center py-8 text-text-muted text-sm">
            No files in this project
          </div>
          
          <div v-else class="text-center py-8 text-text-muted text-sm">
            Select a project to see files
          </div>
        </div>
      </div>
    </div>

    <!-- Watched Files List -->
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-text-primary mb-4">Watched Files</h2>
    </div>

    <div v-if="store.watchedFiles.length === 0" class="bg-bg-secondary border border-border rounded-2xl p-12 text-center">
      <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-bg-tertiary flex items-center justify-center">
        <svg class="w-10 h-10 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      </div>
      <h3 class="text-xl font-semibold text-text-primary mb-2">No files being watched</h3>
      <p class="text-text-secondary mb-6">Browse your team projects above or add a file by key</p>
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

    <!-- Add File Modal (Manual) -->
    <Teleport to="body">
      <div
        v-if="showAddModal"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        @click.self="showAddModal = false"
      >
        <div class="bg-bg-secondary border border-border rounded-2xl p-6 w-full max-w-md animate-slide-up">
          <h2 class="text-xl font-semibold text-text-primary mb-4">Add Figma File by Key</h2>
          
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
              <label class="block text-sm text-text-secondary mb-2">Display Name (optional)</label>
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
