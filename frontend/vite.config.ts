import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = `http://localhost:${process.env.CAMMY_API_PORT ?? 8000}`

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/video/stream': {
        target: apiTarget,
        changeOrigin: true,
        // disable response buffering for the MJPEG stream
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no'
          })
        },
      },
      '/api': apiTarget,
      '/ws': {
        target: 'ws://localhost:8765',
        ws: true,
      },
    },
  },
})