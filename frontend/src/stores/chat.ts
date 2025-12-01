import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: string[]
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const currentFileKey = ref<string | null>(null)

  async function sendMessage(content: string) {
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMessage)
    
    isLoading.value = true
    try {
      const response = await api.post('/chat', {
        message: content,
        file_key: currentFileKey.value,
        conversation_history: messages.value.slice(-10).map(m => ({
          role: m.role,
          content: m.content,
        })),
      })
      
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.data.message,
        timestamp: new Date().toISOString(),
        sources: response.data.sources,
      }
      messages.value.push(assistantMessage)
    } catch (e: any) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      }
      messages.value.push(errorMessage)
    } finally {
      isLoading.value = false
    }
  }

  function setFileContext(fileKey: string | null) {
    currentFileKey.value = fileKey
  }

  function clearMessages() {
    messages.value = []
  }

  return {
    messages,
    isLoading,
    currentFileKey,
    sendMessage,
    setFileContext,
    clearMessages,
  }
})

