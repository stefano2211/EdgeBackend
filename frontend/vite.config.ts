import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const API_TARGET = env.VITE_API_URL || 'http://localhost:8000'

  return {
    plugins: [
      vue(),
      vueDevTools(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
    server: {
      proxy: {
        // API routes
        '/api/v1': {
          target: API_TARGET,
          changeOrigin: true,
        },
        // Public webhook receiver (no /api/v1 prefix)
        '/webhooks': {
          target: API_TARGET,
          changeOrigin: true,
        },
      },
    },
  }
})
