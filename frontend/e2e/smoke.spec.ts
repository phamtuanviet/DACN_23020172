import { expect, test } from "@playwright/test";

// Smoke test chạy sau mỗi lần deploy (docs mục 11.5); ở production chỉ kiểm tra đọc.
test("trang chủ hiển thị", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("healthz trả ok", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.ok()).toBeTruthy();
});
