import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/static/app/',
  plugins: [react()],
  build: { outDir: '../cps/static/app', emptyOutDir: true },
})
