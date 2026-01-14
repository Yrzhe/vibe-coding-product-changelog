import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    preserveSymlinks: true,
  },
  server: {
    port: 3000,
    fs: {
      // Allow serving files from project root (for symlinks)
      allow: [
        path.resolve(__dirname, '..'),
        path.resolve(__dirname, './'),
      ],
    },
    proxy: {
      // 代理 API 请求到后端服务器
      '/api': {
        target: 'http://localhost:3003',
        changeOrigin: true,
      },
    },
  },
})
