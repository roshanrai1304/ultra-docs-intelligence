import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API = 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/upload':  { target: API, changeOrigin: true, timeout: 300000 },  // 5 min — model download on first run
      '/ask':     { target: API, changeOrigin: true, timeout: 60000  },  // 60s
      '/extract': { target: API, changeOrigin: true, timeout: 60000  },  // 60s
      '/health':  { target: API, changeOrigin: true, timeout: 5000   },
    },
  },
})
