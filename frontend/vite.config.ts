import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { cpSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

// Du lieu JSON nam o <repo>/data; khi build duoc chep vao dist/data (GitHub Pages phuc vu cung trang).
const here = import.meta.dirname
const dataDir = process.env.HUB_DATA_DIR ?? resolve(here, '../data')

export default defineConfig({
  base: process.env.HUB_BASE ?? '/Amibroker/',
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'hub-data',
      configureServer(server) {
        // dev: phuc vu <repo>/data tai /Amibroker/data
        server.middlewares.use((req, res, next) => {
          const base = server.config.base.replace(/\/$/, '')
          const url = (req.url ?? '').split('?')[0]
          if (!url.startsWith(base + '/data/')) return next()
          const file = resolve(dataDir, decodeURIComponent(url.slice(base.length + 6)))
          if (!file.startsWith(dataDir) || !existsSync(file)) {
            res.statusCode = 404
            return res.end()
          }
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          import('node:fs').then((fs) => fs.createReadStream(file).pipe(res))
        })
      },
      closeBundle() {
        if (existsSync(dataDir)) cpSync(dataDir, resolve(here, 'dist/data'), { recursive: true })
      },
    },
  ],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
})
