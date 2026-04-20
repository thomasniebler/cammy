import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/video/stream': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // disable response buffering for the MJPEG stream
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no'
          })
        },
      },
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8765',
        ws: true,
      },
    },
  },
})