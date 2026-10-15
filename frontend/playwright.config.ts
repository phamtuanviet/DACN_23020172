import { defineConfig, devices } from "@playwright/test";

// E2E chạy trên development (mặc định) hoặc trên staging: E2E_BASE_URL=https://staging... npm run e2e
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-360", use: { ...devices["Galaxy S9+"], viewport: { width: 360, height: 740 } } },
  ],
});
