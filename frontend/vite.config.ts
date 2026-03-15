import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend port is set by the startup script, defaults to 8000
const backendPort = process.env.BACKEND_PORT || '8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
})
