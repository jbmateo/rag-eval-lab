import { defineConfig } from "@playwright/test";

// Serves the static export (`npm run build` → out/) exactly as it will be hosted.
export default defineConfig({
  testDir: "e2e",
  use: { baseURL: "http://localhost:4173" },
  webServer: { command: "npx serve out -l 4173 --no-clipboard", url: "http://localhost:4173", reuseExistingServer: false },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "mobile", use: { viewport: { width: 375, height: 812 } } },
  ],
});
