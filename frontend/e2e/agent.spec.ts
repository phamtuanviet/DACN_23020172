import { expect, test, type Page } from "@playwright/test";

// Sprint 4: khung chat của trợ lý trên giao diện thật (FR-AGT-01, 04; AC-12, AC-13 phần giao diện;
// NFR-11 ở 360 px).
// Cần backend chạy mô hình giả theo luật (LLM_PROVIDER=fake, không gọi LLM thật):
//   LLM_PROVIDER=fake docker compose up -d backend && E2E_FAKE_LLM=1 npm run e2e
// Chất lượng trả lời của mô hình thật đo bằng bộ kịch bản backend/tests/agent_eval.
test.skip(process.env.E2E_FAKE_LLM !== "1", "cần backend chạy LLM_PROVIDER=fake (E2E_FAKE_LLM=1)");

const PANEL = { name: "Trợ lý đặt lịch" };

async function register(page: Page, email: string) {
  await page.goto("/register");
  await page.getByLabel("Họ và tên").fill("Người Hỏi Trợ Lý");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Số điện thoại").fill("0912 345 678");
  await page.getByLabel("Ngày sinh").fill("12031994");
  await page.getByText("Nữ", { exact: true }).click();
  await page.getByLabel("Mật khẩu", { exact: true }).fill("matkhau123");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /Tạo tài khoản/ }).click();
  await expect(page.getByRole("heading", { name: "Lịch của tôi" })).toBeVisible();
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

test("đặt lịch qua trợ lý: chọn khung, chưa xác nhận thì chưa có lịch, xác nhận thì có", async ({
  page,
}, testInfo) => {
  // Một project: luồng đầy đủ trên máy tính, rồi thu cửa sổ về 360 px để kiểm bố cục điện thoại.
  test.skip(testInfo.project.name !== "desktop", "chạy trên máy tính, tự thu về 360 px");
  await register(page, `agent-${Date.now()}@example.com`);
  await expect(page.getByRole("tab", { name: "Sắp tới (0)" })).toBeVisible();

  await page.getByRole("button", { name: "Hỏi trợ lý" }).click();
  const panel = page.getByRole("complementary", PANEL);
  await expect(panel.getByText("Còn 50 tin nhắn hôm nay")).toBeVisible();
  await expect(panel.getByText("Bạn muốn làm gì?")).toBeVisible();

  await panel.getByLabel("Tin nhắn cho trợ lý").fill("Tôi muốn khám da liễu sáng thứ Bảy tuần sau");
  await panel.getByRole("button", { name: "Gửi" }).click();
  await expect(panel.getByText(/^Đã tìm khung trống sáng Thứ Bảy/)).toBeVisible();
  await expect(panel.getByText("Còn 49 tin nhắn hôm nay")).toBeVisible();

  await panel
    .getByRole("button", { name: /^Chọn khung giờ: Thứ Bảy/ })
    .first()
    .click();
  const card = panel.getByRole("region", { name: "Đề xuất đặt lịch" });
  await expect(card).toBeVisible();
  await expect(card.getByRole("timer")).toContainText(/Còn 0\d:\d\d/);

  // AC-13: thẻ đang chờ thì "Lịch của tôi" vẫn trống; khung chat giữ nguyên khi chuyển trang.
  await page.reload();
  await expect(page.getByRole("tab", { name: "Sắp tới (0)" })).toBeVisible();
  await page.getByRole("button", { name: "Hỏi trợ lý" }).click();
  await expect(card.getByRole("button", { name: "Xác nhận đặt lịch" })).toBeVisible();

  await card.getByRole("button", { name: "Xác nhận đặt lịch" }).click();
  const done = panel.getByRole("status").filter({ hasText: "Đã đặt lịch LH-" });
  await expect(done).toBeVisible();
  const code = (await done.locator("b").textContent())?.replace("Đã đặt lịch ", "") ?? "";
  // AC-12: lịch hiện ngay trong "Lịch của tôi" (không tải lại trang), ghi rõ đặt qua trợ lý.
  await expect(page.getByRole("tab", { name: "Sắp tới (1)" })).toBeVisible();
  await expect(page.getByText(code).first()).toBeVisible();
  await expect(page.getByText("Đặt qua trợ lý").first()).toBeVisible();
  await noHorizontalScroll(page);

  // Điện thoại 360 px (cùng phiên đăng nhập, vì /auth/login và /auth/register giới hạn theo IP):
  // khung chat chiếm toàn màn hình, tab Trợ lý mở lại khung chat với hội thoại cũ.
  await page.setViewportSize({ width: 360, height: 740 });
  const box = await panel.boundingBox();
  expect(box?.width).toBe(360);
  await noHorizontalScroll(page);
  await panel.getByRole("button", { name: "Đóng trợ lý" }).click();
  await expect(panel).toBeHidden();
  const tabs = page.getByRole("navigation", { name: "Điều hướng trên điện thoại" });
  await tabs.getByRole("button", { name: "Trợ lý" }).click();
  await expect(done).toBeVisible();
  await panel.getByLabel("Tin nhắn cho trợ lý").fill("Cho tôi gặp nhân viên");
  await panel.getByRole("button", { name: "Gửi" }).click();
  await expect(panel.getByText("Đã gửi yêu cầu cho nhân viên")).toBeVisible();
  await noHorizontalScroll(page);
});
