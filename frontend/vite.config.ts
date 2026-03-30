import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/offer': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/camera': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/load_usd': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:30000',
        ws: true,
        rewriteWsOrigin: true,
        rewrite: (path) => path.replace(/^\/ws/, ''),
      },
      '/video_feed': {
        target: 'ws://127.0.0.1:8080',
        ws: true,
      },
    },
  },
})
