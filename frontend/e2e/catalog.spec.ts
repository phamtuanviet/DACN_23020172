import { expect, test } from "@playwright/test";

// Sprint 2: tìm dịch vụ có dấu hay không dấu (FR-CAT-04), hồ sơ bác sĩ có giờ trống thật 7 ngày
// tới (UC03, FR-SCH-01..03), wizard giữ lựa chọn trên URL (docs mục 9.3).
// Dùng dữ liệu seed (@demo.local) nên chỉ chạy trên development và staging. Mỗi project chỉ đăng
// nhập một lần, vì /auth/login giới hạn 10 lần/phút/IP và auth.spec.ts đã dùng phần lớn.
const DEMO_PASSWORD = "Demo12345";

test("gõ da lieu không dấu ra đúng các dịch vụ Da liễu", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("searchbox").fill("da lieu");
  await page.getByRole("button", { name: "Tìm", exact: true }).click();
  await expect(page).toHaveURL(/\/services\?q=da\+lieu/);
  await expect(page.getByRole("article").getByRole("heading", { level: 3 })).toHaveText([
    "Khám da liễu tổng quát",
    "Tư vấn trị mụn",
    "Khám viêm da cơ địa",
  ]);
  await expect(page.getByRole("link", { name: "Bác sĩ (3)" })).toBeVisible();
});

test("hồ sơ bác sĩ hiện giờ trống của 7 ngày tới và đổi theo dịch vụ", async ({ page }) => {
  await page.goto("/services?q=tran+minh&tab=doctors");
  await page.getByRole("link", { name: /Trần Minh/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "ThS. BS. Trần Minh" })).toBeVisible();

  const days = page.getByRole("tab");
  await expect(days).toHaveCount(7);
  await expect(page.getByRole("tabpanel").getByRole("link").first()).toBeVisible();

  await page.getByText("Khám viêm da cơ địa", { exact: true }).click();
  await expect(page).toHaveURL(/service=\d+/);
  await expect(page.getByText("Khám viêm da cơ địa · 20 phút")).toBeVisible();
});

test("khách bấm giờ trống thì đăng nhập rồi vào thẳng wizard, nút Quay lại đi đúng từng bước", async ({
  page,
}) => {
  await page.goto("/services?q=tran+minh&tab=doctors");
  await page.getByRole("link", { name: /Trần Minh/ }).click();
  const slot = page.getByRole("tabpanel").getByRole("link").first();
  await slot.click();

  await expect(page).toHaveURL(/\/login\?next=%2Fbooking/);
  await page.getByLabel("Email").fill("lan@demo.local");
  await page.getByLabel("Mật khẩu", { exact: true }).fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();

  // Giờ đã chọn trên trang công khai: vào thẳng bước 4 với đủ dịch vụ, bác sĩ, giờ từ URL.
  await expect(page).toHaveURL(/\/booking\?.*doctor=\d+.*start=/);
  await expect(page.getByRole("heading", { name: "Xem lại và xác nhận" })).toBeVisible();
  await expect(page.getByText("ThS. BS. Trần Minh · Da liễu")).toBeVisible();
  await expect(page.getByText("Khám da liễu tổng quát · 20 phút")).toBeVisible();

  // Sửa bác sĩ: về bước 2, chọn "Bác sĩ bất kỳ" rồi tiếp tục sang bước chọn ngày giờ.
  await page.getByRole("link", { name: "Sửa bác sĩ" }).click();
  await expect(page.getByRole("heading", { name: "Chọn bác sĩ" })).toBeVisible();
  await page.getByRole("radio", { name: /Bác sĩ bất kỳ/ }).check();
  await page.getByRole("button", { name: "Tiếp tục: chọn ngày giờ" }).click();
  await expect(page).toHaveURL(/doctor=any/);
  const summary = page.getByRole("complementary", { name: "Lịch hẹn của bạn" });
  await expect(summary.getByText("Bác sĩ bất kỳ")).toBeVisible();

  await page.goBack();
  await expect(page.getByRole("heading", { name: "Chọn bác sĩ" })).toBeVisible();
  await page.getByRole("link", { name: "Quay lại" }).click();
  await expect(page.getByRole("heading", { name: "Bạn muốn khám gì?" })).toBeVisible();
  await expect(page.getByRole("radio", { name: /Da liễu/ })).toHaveAttribute(
    "aria-checked",
    "true",
  );
});
