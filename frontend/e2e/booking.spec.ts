import { expect, test, type Page } from "@playwright/test";

// Sprint 3, AC-01: bệnh nhân mới đăng ký, chọn dịch vụ → bác sĩ → khung giờ → xác nhận, thấy lịch
// trong "Sắp tới"; rồi tự đổi và hủy lịch (UC06, UC07). Chạy cả máy tính và điện thoại 360 px
// (NFR-11). Dùng dữ liệu seed nên chỉ chạy trên development và staging. Mỗi project đăng ký đúng
// một tài khoản vì /auth/register giới hạn 5 lần/phút/IP.

async function register(page: Page, email: string) {
  await page.goto("/register?next=%2Fbooking");
  await page.getByLabel("Họ và tên").fill("Người Đặt Thử");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Số điện thoại").fill("0912 345 678");
  await page.getByLabel("Ngày sinh").fill("12031994");
  await page.getByText("Nữ", { exact: true }).click();
  await page.getByLabel("Mật khẩu", { exact: true }).fill("matkhau123");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /Tạo tài khoản/ }).click();
}

async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

/** Chọn ngày còn khung từ ngày mai trở đi: lịch hôm nay có thể đã dưới 2 giờ, không đổi được. */
async function pickLaterDay(page: Page) {
  const calendar = page.getByRole("group", { name: "Chọn ngày khám" });
  const open = calendar.getByRole("button", { name: /\d+ khung$/ });
  await expect(open.first()).toBeVisible();
  if ((await open.count()) < 2) await page.getByRole("button", { name: "Tháng sau" }).click();
  const day = (await open.count()) > 1 ? open.nth(1) : open.first();
  const label = (await day.getAttribute("aria-label")) ?? "";
  await day.click();
  // Ngày chọn nằm trên URL: chờ đổi xong rồi mới chọn giờ, không thì bấm nhầm khung của ngày cũ.
  await expect(calendar.getByRole("button", { name: label })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
}

/** Bấm khung giờ còn trống đầu tiên trong danh sách khung (không tính ô ngày của lịch tháng). */
async function pickFirstSlot(page: Page, scope = page.locator("body")) {
  const slot = scope.getByRole("button", { name: /^\d{2}:\d{2}, / }).first();
  await expect(slot).toBeVisible();
  const label = (await slot.getAttribute("aria-label")) ?? "";
  await slot.click();
  await expect(slot).toHaveAttribute("aria-pressed", "true");
  return label;
}

test("bệnh nhân mới đặt lịch đầu tiên, thấy trong Sắp tới, rồi tự đổi và hủy", async ({
  page,
}, testInfo) => {
  const mobile = testInfo.project.name === "mobile-360";
  await register(page, `e2e-${Date.now()}-${testInfo.project.name}-dat-lich@example.com`);

  // Bước 1: dịch vụ
  await expect(page).toHaveURL(/\/booking$/);
  await page.getByRole("radio", { name: /Da liễu/ }).click();
  await page.getByRole("button", { name: "Chọn Khám da liễu tổng quát" }).click();

  // Bước 2: bác sĩ bất kỳ (mặc định)
  await expect(page.getByRole("heading", { name: "Chọn bác sĩ" })).toBeVisible();
  await page.getByRole("button", { name: "Tiếp tục: chọn ngày giờ" }).click();

  // Bước 3: lịch tháng tự chọn ngày còn khung đầu tiên; chọn giờ và ghi lý do khám
  await expect(page.getByRole("heading", { name: "Chọn ngày và giờ" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Chọn ngày khám" })).toBeVisible();
  if (mobile) await expectNoHorizontalScroll(page);
  await pickLaterDay(page);
  await pickFirstSlot(page);
  await page.getByLabel(/Lý do khám/).fill("Nổi mẩn đỏ ở tay");
  await page.getByRole("button", { name: "Tiếp tục: xem lại" }).click();

  // Bước 4: xem lại rồi xác nhận
  await expect(page.getByRole("heading", { name: "Xem lại và xác nhận" })).toBeVisible();
  await expect(page.getByText("Nổi mẩn đỏ ở tay")).toBeVisible();
  await expect(page.getByText("Người Đặt Thử · 0912 345 678")).toBeVisible();
  if (mobile) await expectNoHorizontalScroll(page);
  await page.getByRole("button", { name: "Xác nhận đặt lịch" }).click();

  // Trang thành công có mã lịch hẹn
  await expect(page.getByRole("heading", { name: "Đã đặt lịch thành công" })).toBeVisible();
  const code = page.getByText(/^LH-\d{6}-[0-9A-HJKMNP-TV-Z]{4}$/);
  await expect(code).toBeVisible();
  const appointmentCode = (await code.textContent()) ?? "";
  if (mobile) await expectNoHorizontalScroll(page);

  // Lịch của tôi: thấy lịch vừa đặt trong Sắp tới (AC-01)
  await page.getByRole("link", { name: "Xem lịch của tôi" }).click();
  await expect(page.getByRole("tab", { name: "Sắp tới (1)" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  const list = page.getByRole("list", { name: "Danh sách lịch hẹn" });
  await expect(list.getByText("Khám da liễu tổng quát")).toBeVisible();
  if (mobile) {
    await expectNoHorizontalScroll(page);
    await list.getByRole("link").first().click();
  }
  const detail = page.getByRole("region", { name: "Chi tiết lịch hẹn" });
  await expect(detail.getByText(appointmentCode)).toBeVisible();
  await expect(detail.getByText("Bạn đặt lịch")).toBeVisible();

  // Đổi lịch: chọn khung khác trong hộp thoại, mã lịch giữ nguyên (UC06)
  await detail.getByRole("button", { name: "Đổi lịch" }).click();
  const reschedule = page.getByRole("dialog", { name: "Đổi lịch hẹn" });
  await expect(reschedule.getByText(`Mã lịch hẹn giữ nguyên: ${appointmentCode}`)).toBeVisible();
  // Ngày thứ hai còn khung trong dải 14 ngày: khung của hôm nay có thể đã dưới 2 giờ.
  const laterDay = reschedule
    .getByRole("button", { name: /^(T\d|CN) \d{2}\/\d{2}$/, disabled: false })
    .nth(1);
  await laterDay.click();
  await expect(laterDay).toHaveAttribute("aria-pressed", "true");
  await pickFirstSlot(page, reschedule);
  await reschedule.getByRole("button", { name: "Xác nhận đổi lịch" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Đã đổi lịch sang" })).toBeVisible();
  await expect(detail.getByText(/Bạn đổi lịch/)).toBeVisible();

  // Hủy lịch kèm lý do (UC07): lịch chuyển sang tab Lịch sử với trạng thái Đã hủy
  await detail.getByRole("button", { name: "Hủy lịch" }).click();
  const cancel = page.getByRole("dialog", { name: "Hủy lịch hẹn?" });
  await cancel.getByRole("combobox").selectOption("Đặt nhầm giờ");
  await cancel.getByRole("button", { name: "Hủy lịch hẹn" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: `Đã hủy lịch ${appointmentCode}` }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: /Lịch sử/ })).toHaveAttribute("aria-selected", "true");
  await expect(detail.getByText("Đã hủy", { exact: true })).toBeVisible();
  await expect(detail.getByText("Đặt nhầm giờ")).toBeVisible();
});
