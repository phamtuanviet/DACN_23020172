import { expect, test, type Page } from "@playwright/test";

// Luồng tài khoản Sprint 1 (AC-01 phần đăng ký, đăng nhập; FR-AUTH-01..03; docs mục 9.3).
// Dùng tài khoản demo của seed (@demo.local), nên chỉ chạy trên development và staging.
const DEMO_PASSWORD = "Demo12345";

async function login(page: Page, email: string, password: string) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
}

test("đăng ký bệnh nhân mới rồi vào thẳng Lịch của tôi", async ({ page }, testInfo) => {
  const email = `e2e-${Date.now()}-${testInfo.project.name}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Họ và tên").fill("Người Dùng Thử");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Số điện thoại").fill("0912 345 678");
  await page.getByLabel("Ngày sinh").fill("12031994");
  await expect(page.getByLabel("Ngày sinh")).toHaveValue("12/03/1994");
  await page.getByText("Nữ", { exact: true }).click();
  await page.getByLabel("Mật khẩu", { exact: true }).fill("matkhau123");
  await expect(page.getByText("Trung bình")).toBeVisible();

  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page.getByText("Bạn cần đồng ý chính sách xử lý dữ liệu để đăng ký.")).toBeVisible();

  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/me\/appointments$/);
  await expect(page.getByRole("heading", { name: "Lịch của tôi" })).toBeVisible();
});

test("email đã có tài khoản báo ngay tại ô email", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Họ và tên").fill("Nguyễn Thị Lan");
  await page.getByLabel("Email").fill("LAN@demo.local");
  await page.getByLabel("Số điện thoại").fill("0912345678");
  await page.getByLabel("Ngày sinh").fill("12/03/1994");
  await page.getByText("Nữ", { exact: true }).click();
  await page.getByLabel("Mật khẩu", { exact: true }).fill("matkhau123");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page.getByText("Email này đã có tài khoản.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Đăng nhập?" })).toBeVisible();
});

test("sai thông tin đăng nhập chỉ báo lỗi chung", async ({ page }) => {
  await page.goto("/login");
  await login(page, "khongco@demo.local", "saimatkhau1");
  // Next.js cũng có một vùng role="alert" (thông báo chuyển trang), nên lọc theo nội dung.
  await expect(
    page.getByRole("alert").filter({ hasText: "Email hoặc mật khẩu không đúng." }),
  ).toBeVisible();
});

test("chưa đăng nhập mở trang bệnh nhân thì sang đăng nhập, xong quay lại đúng trang", async ({
  page,
}) => {
  await page.goto("/me/appointments");
  await expect(page).toHaveURL(/\/login\?next=%2Fme%2Fappointments$/);
  await login(page, "lan@demo.local", DEMO_PASSWORD);
  await expect(page).toHaveURL(/\/me\/appointments$/);
  await expect(page.getByRole("heading", { name: "Lịch của tôi" })).toBeVisible();
});

test("bác sĩ đăng nhập vào khu vực bác sĩ và đăng xuất được", async ({ page }) => {
  await page.goto("/login");
  await login(page, "minh.tran@demo.local", DEMO_PASSWORD);
  await expect(page).toHaveURL(/\/doctor\/schedule$/);
  await expect(page.getByRole("heading", { name: "Lịch khám" })).toBeVisible();

  const logoutButton = page.getByRole("button", { name: "Đăng xuất" });
  if (!(await logoutButton.isVisible()))
    await page.getByRole("button", { name: "Mở menu" }).click();
  await logoutButton.click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goto("/doctor/schedule");
  await expect(page).toHaveURL(/\/login\?next=%2Fdoctor%2Fschedule$/);
});

test("bệnh nhân mở trang quản trị thấy thông báo không có quyền", async ({ page }) => {
  await page.goto("/login");
  await login(page, "lan@demo.local", DEMO_PASSWORD);
  await expect(page).toHaveURL(/\/me\/appointments$/);
  await page.goto("/admin/catalog");
  await expect(
    page.getByRole("heading", { name: "Bạn không có quyền xem trang này" }),
  ).toBeVisible();
});
