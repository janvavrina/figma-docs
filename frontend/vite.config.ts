import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Detect if running in Docker (backend hostname) or local dev
const apiTarget = process.env.DOCKER_ENV === 'true' 
  ? 'http://backend:8000'
  : 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/screenshots': {
        target: apiTarget,
        changeOrigin: true,
      }
    }
  }
})
