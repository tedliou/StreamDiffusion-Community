import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The production build is committed inside the Python package, so running the Runtime never needs Node (ADR-0007).
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../src/streamturbo/web_panel",
    emptyOutDir: true,
    assetsInlineLimit: 0,
  },
  server: {
    proxy: { "/ws": { target: "ws://127.0.0.1:8765", ws: true } },
  },
});
