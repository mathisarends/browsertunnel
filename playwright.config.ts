import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "frontend/tests",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:15173",
    channel: process.platform === "win32" ? "chrome" : undefined,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: [
    {
      command:
        "uv run --locked python -m uvicorn browsertunnel.app:app --host 127.0.0.1 --port 18000",
      url: "http://127.0.0.1:18000/api/browser/openrpc.json",
      timeout: 30000,
    },
    {
      command:
        "npm exec vite -- --config frontend/vite.config.ts --host 127.0.0.1 --port 15173",
      url: "http://127.0.0.1:15173",
      env: { BROWSER_TUNNEL_API_URL: "http://127.0.0.1:18000" },
    },
  ],
});
