import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("framer-motion") || id.includes("lenis") || id.includes("gsap")) return "motion";
          if (id.includes("@supabase")) return "supabase";
          if (id.includes("lucide-react")) return "icons";
          if (id.includes("react-dom") || id.includes("react-router") || id.includes("/react/")) {
            return "react-core";
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
