import { defineConfig } from "vite";

export default defineConfig({
  root: __dirname,
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "../dist/frontend",
    emptyOutDir: true,
  },
});
