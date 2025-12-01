<script setup lang="ts">
import { RouterView } from 'vue-router'
import Sidebar from './components/Sidebar.vue'
import ChatWidget from './components/ChatWidget.vue'
</script>

<template>
  <div class="min-h-screen bg-bg-primary flex">
    <Sidebar />
    <main class="flex-1 ml-64">
      <RouterView />
    </main>
    <ChatWidget />
  </div>
</template>

