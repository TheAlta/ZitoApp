import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build is committed to landing/app and served by FastAPI under /landing-static/app/.
export default defineConfig({
  plugins: [react()],
  base: "/landing-static/app/",
  build: {
    outDir: "../landing/app",
    emptyOutDir: true,
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 900,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8010",
      "/landing-static": { target: "http://127.0.0.1:8010", bypass: (req) => (req.url.startsWith("/landing-static/app/") ? req.url : undefined) },
    },
  },
});
