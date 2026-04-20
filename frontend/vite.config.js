import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    // Relative asset paths so CloudFront sub-path deployments work
    assetsDir: "assets",
    sourcemap: false,
  },
  server: {
    port: 3000,
  },
});
