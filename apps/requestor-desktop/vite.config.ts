import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const appDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(appDir, "../..");

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "next/link": path.resolve(appDir, "src/shims/next-link.tsx"),
      "next/navigation": path.resolve(appDir, "src/shims/next-navigation.ts"),
    },
  },
  server: {
    fs: {
      allow: [repoRoot],
    },
  },
});
