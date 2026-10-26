import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq) => {
            // Strip oversized localhost cookies if any
            proxyReq.removeHeader("cookie");
          });
        }
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("proxyReqWs", (proxyReq) => {
            // Strip oversized localhost cookies to prevent 431 Request Header Fields Too Large
            proxyReq.removeHeader("cookie");
          });
        }
      }
    }
  }
});
