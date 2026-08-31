import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend talks to the API through a /api prefix that this proxy strips.
// Inside Docker the target must be the service name, not localhost — a
// container's localhost is itself.
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirrors the `paths` entry in tsconfig.json. tsc reads that file; Vite
    // does not, so the alias has to be declared in both or the build fails
    // while the type check passes.
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
