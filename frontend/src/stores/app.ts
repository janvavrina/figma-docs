import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export interface WatchedFile {
  file_key: string
  name: string
  last_version: string | null
  last_modified: string | null
  last_checked: string | null
  doc_generated: boolean
}

export interface Documentation {
  id: string
  figma_file_key: string
  figma_file_name: string
  title: string
  doc_type: string
  created_at: string
  updated_at: string
  version: string
  figma_version: string | null
  content?: string
}

export interface SystemStatus {
  status: string
  change_detection: {
    running: boolean
    polling_interval_minutes: number
    watched_files_count: number
  }
  config: {
    ollama_url: string
    default_model: string
  }
}

export const useAppStore = defineStore('app', () => {
  // State
  const watchedFiles = ref<WatchedFile[]>([])
  const documentation = ref<Documentation[]>([])
  const systemStatus = ref<SystemStatus | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const chatOpen = ref(false)

  // Getters
  const hasWatchedFiles = computed(() => watchedFiles.value.length > 0)
  const hasDocumentation = computed(() => documentation.value.length > 0)
  const isChangeDetectionRunning = computed(() => systemStatus.value?.change_detection.running ?? false)

  // Actions
  async function fetchStatus() {
    try {
      const response = await api.get('/status')
      systemStatus.value = response.data
    } catch (e) {
      console.error('Failed to fetch status:', e)
    }
  }

  async function fetchWatchedFiles() {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.get('/figma/files')
      watchedFiles.value = response.data
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch watched files'
    } finally {
      isLoading.value = false
    }
  }

  async function addWatchedFile(fileKey: string, name: string) {
    isLoading.value = true
    error.value = null
    try {
      await api.post('/figma/files', { file_key: fileKey, name })
      await fetchWatchedFiles()
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message || 'Failed to add file'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function removeWatchedFile(fileKey: string) {
    isLoading.value = true
    error.value = null
    try {
      await api.delete(`/figma/files/${fileKey}`)
      await fetchWatchedFiles()
    } catch (e: any) {
      error.value = e.message || 'Failed to remove file'
    } finally {
      isLoading.value = false
    }
  }

  async function fetchDocumentation() {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.get('/docs')
      documentation.value = response.data
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch documentation'
    } finally {
      isLoading.value = false
    }
  }

  async function generateDocumentation(fileKey: string, docType: string = 'both') {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.post('/docs/generate', {
        file_key: fileKey,
        doc_type: docType,
        formats: ['markdown', 'html'],
      })
      await fetchDocumentation()
      return response.data
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message || 'Failed to generate documentation'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function generateVisionDocumentation(fileKey: string, docType: string = 'both', visionModel?: string) {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.post('/docs/generate-vision', {
        file_key: fileKey,
        doc_type: docType,
        formats: ['markdown', 'html'],
        vision_model: visionModel,
      })
      await fetchDocumentation()
      return response.data
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message || 'Failed to generate vision documentation'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function getDocumentation(docId: string): Promise<Documentation | null> {
    try {
      const response = await api.get(`/docs/${docId}`)
      return response.data
    } catch (e) {
      console.error('Failed to get documentation:', e)
      return null
    }
  }

  async function startChangeDetection() {
    try {
      await api.post('/detection/start')
      await fetchStatus()
    } catch (e) {
      console.error('Failed to start change detection:', e)
    }
  }

  async function stopChangeDetection() {
    try {
      await api.post('/detection/stop')
      await fetchStatus()
    } catch (e) {
      console.error('Failed to stop change detection:', e)
    }
  }

  async function checkAllFiles() {
    isLoading.value = true
    try {
      const response = await api.post('/detection/check-all')
      await fetchWatchedFiles()
      return response.data
    } catch (e) {
      console.error('Failed to check files:', e)
      return []
    } finally {
      isLoading.value = false
    }
  }

  function toggleChat() {
    chatOpen.value = !chatOpen.value
  }

  return {
    // State
    watchedFiles,
    documentation,
    systemStatus,
    isLoading,
    error,
    chatOpen,
    // Getters
    hasWatchedFiles,
    // Actions
    generateVisionDocumentation,
    hasDocumentation,
    isChangeDetectionRunning,
    // Actions
    fetchStatus,
    fetchWatchedFiles,
    addWatchedFile,
    removeWatchedFile,
    fetchDocumentation,
    generateDocumentation,
    getDocumentation,
    startChangeDetection,
    stopChangeDetection,
    checkAllFiles,
    toggleChat,
  }
})

