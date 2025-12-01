<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'

const appStore = useAppStore()
const chatStore = useChatStore()

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const sendMessage = async () => {
  if (!inputMessage.value.trim() || chatStore.isLoading) return
  
  const message = inputMessage.value
  inputMessage.value = ''
  
  await chatStore.sendMessage(message)
  scrollToBottom()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, scrollToBottom)
</script>

<template>
  <!-- Chat Toggle Button -->
  <button
    @click="appStore.toggleChat"
    class="fixed bottom-6 right-6 w-14 h-14 bg-accent hover:bg-accent-hover rounded-full shadow-lg flex items-center justify-center transition-all duration-300 z-50"
    :class="{ 'rotate-90': appStore.chatOpen }"
  >
    <svg v-if="!appStore.chatOpen" class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
    <svg v-else class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
    </svg>
  </button>

  <!-- Chat Panel -->
  <Transition name="slide-up">
    <div
      v-if="appStore.chatOpen"
      class="fixed bottom-24 right-6 w-96 h-[500px] bg-bg-secondary border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden z-40"
    >
      <!-- Header -->
      <div class="p-4 border-b border-border bg-bg-tertiary">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-gradient-to-br from-accent to-purple-400 flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div>
            <h3 class="font-semibold text-text-primary">Docs Assistant</h3>
            <p class="text-xs text-text-muted">Ask about your documentation</p>
          </div>
        </div>
      </div>

      <!-- Messages -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto p-4 space-y-4"
      >
        <div v-if="chatStore.messages.length === 0" class="text-center py-8">
          <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-bg-tertiary flex items-center justify-center">
            <svg class="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <p class="text-text-secondary text-sm">Start a conversation!</p>
          <p class="text-text-muted text-xs mt-1">Ask about your Figma designs or documentation</p>
        </div>

        <div
          v-for="(message, index) in chatStore.messages"
          :key="index"
          class="flex"
          :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[80%] rounded-2xl px-4 py-2"
            :class="message.role === 'user' 
              ? 'bg-accent text-white rounded-br-md' 
              : 'bg-bg-tertiary text-text-primary rounded-bl-md'"
          >
            <p class="text-sm whitespace-pre-wrap">{{ message.content }}</p>
            <p class="text-xs mt-1 opacity-60">
              {{ new Date(message.timestamp).toLocaleTimeString() }}
            </p>
          </div>
        </div>

        <!-- Loading indicator -->
        <div v-if="chatStore.isLoading" class="flex justify-start">
          <div class="bg-bg-tertiary rounded-2xl rounded-bl-md px-4 py-3">
            <div class="flex gap-1">
              <div class="w-2 h-2 bg-text-muted rounded-full animate-bounce" style="animation-delay: 0ms"></div>
              <div class="w-2 h-2 bg-text-muted rounded-full animate-bounce" style="animation-delay: 150ms"></div>
              <div class="w-2 h-2 bg-text-muted rounded-full animate-bounce" style="animation-delay: 300ms"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="p-4 border-t border-border">
        <form @submit.prevent="sendMessage" class="flex gap-2">
          <input
            v-model="inputMessage"
            type="text"
            placeholder="Ask about your docs..."
            class="flex-1 bg-bg-tertiary border border-border rounded-xl px-4 py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent transition-colors"
            :disabled="chatStore.isLoading"
          />
          <button
            type="submit"
            class="w-12 h-12 bg-accent hover:bg-accent-hover rounded-xl flex items-center justify-center transition-colors disabled:opacity-50"
            :disabled="!inputMessage.trim() || chatStore.isLoading"
          >
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>

