import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

import path from 'node:path'

export default defineConfig(({ mode }) => {
  // 从项目根目录（上一级）加载 .env
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '')
  const backendHost = env.BACKEND_HOST || 'localhost'
  const backendPort = env.BACKEND_PORT || '8000'
  const frontendHost = env.FRONTEND_HOST || '0.0.0.0'
  const frontendPort = Number(env.FRONTEND_PORT || '5173')
  const backendUrl = `http://${backendHost === '0.0.0.0' ? 'localhost' : backendHost}:${backendPort}`

  return {
    plugins: [vue()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      host: frontendHost,
      port: frontendPort,
      proxy: {
        '/api': { target: backendUrl, changeOrigin: true },
        '/docs/public': { target: backendUrl, changeOrigin: true },
        '/v1': { target: backendUrl, changeOrigin: true },
        '/xpay': { target: backendUrl, changeOrigin: true },
        '/static': { target: backendUrl, changeOrigin: true },
      },
    },
    build: {
      outDir: '../app/static/spa',
      emptyOutDir: true,
    },
  }
})
