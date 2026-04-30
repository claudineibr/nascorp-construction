import react from "@vitejs/plugin-react"
import federation from "@originjs/vite-plugin-federation"
import { defineConfig } from "vite"


export default defineConfig({
  plugins: [
    react(),
    federation({
      name: "constructionMfe",
      filename: "remoteEntry.js",
      exposes: {
        "./ConstructionApp": "./src/App.jsx",
      },
      shared: ["react", "react-dom"],
    }),
  ],
  server: {
    host: "127.0.0.1",
    port: 8011,
  },
  build: {
    target: "esnext",
  },
})