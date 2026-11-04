import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
// From vitest/config, not vite — `defineConfig` from vite does not type `test`.
import { defineConfig } from "vitest/config";

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
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Only files under src/test. Keeping tests out of the component tree means
    // `tsc -b` for the production build does not have to exclude them.
    include: ["src/test/**/*.test.ts", "src/test/**/*.test.tsx"],
    restoreMocks: true,
  },
});
