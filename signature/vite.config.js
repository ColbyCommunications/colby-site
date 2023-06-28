import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    assetsDir: "signature-assets", // Specify the desired assets folder name
  },
  plugins: [react()],
});
