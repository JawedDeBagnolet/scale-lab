import { defineConfig } from 'vite'

export default defineConfig({
  // Static site: public/ files are copied as-is to dist/
  // index.html redirects to Module Dashboard v1.dc.html
  server: { port: 5173 },
})
