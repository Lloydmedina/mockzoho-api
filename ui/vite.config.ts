import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/ui/',
  server: {
    port: 5173,
    proxy: {
      '/crm': 'http://localhost:8091',
      '/oauth': 'http://localhost:8091',
      '/__mock__': 'http://localhost:8091',
      '/openapi.json': 'http://localhost:8091',
    },
  },
  build: {
    outDir: '../app/static/ui',
    emptyOutDir: true,
  },
})
