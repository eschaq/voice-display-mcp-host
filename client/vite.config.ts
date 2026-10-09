import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The client talks to the host on another port in development and from the
// same origin in production, so every call is a relative path and the proxy
// below is the only place the development port appears.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/turn": "http://127.0.0.1:8080",
      "/speak": "http://127.0.0.1:8080",
      "/card": "http://127.0.0.1:8080",
      "/health": "http://127.0.0.1:8080",
    },
  },
  build: { outDir: "dist" },
});
