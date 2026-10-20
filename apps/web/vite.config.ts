import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Static site: public/ files are copied as-is to dist/
  // index.html redirects to Module Dashboard v1.dc.html
  server: { port: 5173 },
})
