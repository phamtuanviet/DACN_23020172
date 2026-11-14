import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";

// Sprint 6 (AC-20; PRD mục 2 "Hiệu quả của Agent"): cùng bốn tác vụ làm trên web và qua trợ lý,
// ghi hoàn thành hay lỗi, số lần bấm, số ký tự gõ, thời gian. Không chạy trong bộ e2e thường ngày:
//   E2E_COMPARE=1 npx playwright test e2e/compare.spec.ts --project=desktop          (chỉ web)
//   E2E_COMPARE=1 E2E_COMPARE_AGENT=1 npx playwright test e2e/compare.spec.ts --project=desktop
// Phần trợ lý cần backend chạy LLM thật (tốn phí, xem backend/tests/agent_eval/README.md). Kết
// quả ghi vào test-results/compare/ (không commit), kèm bảng Markdown để chép vào báo cáo.
//
// Máy bấm nhanh hơn người nhiều, nên ngoài thời gian chờ hệ thống đo được (tải trang, chờ trợ lý)
// còn ước thời gian thao tác của người theo Keystroke-Level Model (Card, Moran, Newell 1980).
test.skip(process.env.E2E_COMPARE !== "1", "chỉ chạy khi đo so sánh: E2E_COMPARE=1");
test.describe.configure({ mode: "serial" });

const AGENT = process.env.E2E_COMPARE_AGENT === "1";
const AGENT_TIMEOUT = 60_000; // một lượt trợ lý tối đa 30 giây, cộng thời gian tạo thẻ
const WEEKDAY_SHORT = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

// KLM: M chuẩn bị 1,35 s trước mỗi thao tác; P trỏ chuột 1,1 s; B bấm nút 0,2 s; H chuyển tay
// giữa chuột và bàn phím 0,4 s; K gõ một ký tự 0,28 s (người gõ trung bình).
const KLM = { M: 1.35, P: 1.1, B: 0.2, H: 0.4, K: 0.28 };

// T2 nhiều ràng buộc (bác sĩ cụ thể, buổi chiều, ngày sớm nhất tuần sau) là loại tác vụ PRD kỳ
// vọng trợ lý giúp ít thao tác hơn. T3, T4 làm trên lịch của T2.
const TASKS = {
  T1: "Đặt khám da liễu tổng quát, bác sĩ bất kỳ, khung sớm nhất từ ngày mai",
  T2: "Đặt khám da liễu với BS.CKI Nguyễn Thu Hà, buổi chiều, ngày sớm nhất của tuần sau",
  T3: "Dời lịch của T2 sang buổi sáng cùng ngày, vẫn bác sĩ đó",
  T4: "Hủy lịch của T2, lý do bận việc đột xuất",
} as const;
type Task = keyof typeof TASKS;

const AGENT_MESSAGES: Record<Task, string> = {
  T1: "Tôi muốn khám da liễu tổng quát, bác sĩ nào cũng được, khung sớm nhất từ ngày mai",
  T2: "Tôi muốn khám da liễu với bác sĩ Thu Hà vào buổi chiều, ngày sớm nhất trong tuần sau",
  T3: "Dời lịch khám buổi chiều với bác sĩ Thu Hà của tôi sang buổi sáng cùng ngày, vẫn bác sĩ đó",
  T4: "Hủy lịch khám với bác sĩ Thu Hà của tôi, tôi bận việc đột xuất",
};
const CONFIRM: Record<Task, string> = {
  T1: "Xác nhận đặt lịch",
  T2: "Xác nhận đặt lịch",
  T3: "Xác nhận đổi",
  T4: "Xác nhận hủy lịch",
};

type Measure = {
  task: Task;
  channel: "web" | "agent";
  success: boolean;
  clicks: number;
  keystrokes: number;
  waited_s: number;
  klm_s: number;
  total_s: number;
  error?: string;
};

/** Ghi lại thao tác của người dùng (bấm, gõ) để đếm và ước thời gian theo KLM. */
class Recorder {
  clicks = 0;
  keystrokes = 0;
  private klm = 0;
  private readonly started = performance.now();

  async click(target: Locator) {
    this.count();
    await target.click();
  }

  /** Thao tác không phải một lần bấm của Playwright (chọn trong danh sách thả xuống). */
  count() {
    this.clicks += 1;
    this.klm += KLM.M + KLM.P + KLM.B;
  }

  async type(target: Locator, text: string) {
    this.keystrokes += text.length;
    this.klm += KLM.M + KLM.H + text.length * KLM.K + KLM.H;
    await target.fill(text);
  }

  measure(task: Task, channel: Measure["channel"], error?: string): Measure {
    const round = (value: number) => Math.round(value * 10) / 10;
    const waited = (performance.now() - this.started) / 1000;
    return {
      task,
      channel,
      success: error === undefined,
      clicks: this.clicks,
      keystrokes: this.keystrokes,
      waited_s: round(waited),
      klm_s: round(this.klm),
      total_s: round(waited + this.klm),
      error,
    };
  }
}

const results: Measure[] = [];
const stamp = new Date().toISOString().replace(/[:.]/g, "-");

async function run(
  task: Task,
  channel: Measure["channel"],
  work: (rec: Recorder) => Promise<void>,
) {
  const rec = new Recorder();
  try {
    await work(rec);
    results.push(rec.measure(task, channel));
  } catch (error) {
    results.push(rec.measure(task, channel, String(error).split("\n")[0]));
  }
}

/** Ghi kết quả tới thời điểm này (JSON và bảng Markdown) vào test-results/compare/. */
function save(testInfo: TestInfo) {
  const header =
    "| Tác vụ | Kênh | Kết quả | Lần bấm | Ký tự gõ | Chờ hệ thống (s) | Thao tác ước tính KLM (s) | Tổng (s) |";
  const rows = results.map(
    (r) =>
      `| ${r.task} | ${r.channel === "web" ? "Web" : "Trợ lý"} | ${r.success ? "xong" : `lỗi: ${r.error}`} | ` +
      `${r.clicks} | ${r.keystrokes} | ${r.waited_s} | ${r.klm_s} | ${r.total_s} |`,
  );
  const tasks = Object.entries(TASKS).map(([id, text]) => `- ${id}: ${text}`);
  const table = [
    header,
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ...rows,
    "",
    ...tasks,
  ];
  const folder = join(testInfo.config.rootDir, "..", "test-results", "compare");
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, `web-vs-agent-${stamp}.json`), JSON.stringify(results, null, 2));
  writeFileSync(join(folder, `web-vs-agent-${stamp}.md`), `${table.join("\n")}\n`);
}

// ---------------------------------------------------------------------------- dùng chung
/** Ngày theo giờ Việt Nam cách hôm nay `offset` ngày, dạng YYYY-MM-DD. */
function clinicDay(offset = 0): string {
  const moment = new Date(Date.now() + offset * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(moment);
}

function addDays(day: string, days: number): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);
}

/** Thứ Hai của tuần sau. */
function nextMonday(): string {
  const today = clinicDay();
  return addDays(today, 8 - (new Date(`${today}T00:00:00Z`).getUTCDay() || 7));
}

/** "26/10" */
function dayMonth(day: string): string {
  return `${day.slice(8, 10)}/${day.slice(5, 7)}`;
}

async function register(page: Page, label: string) {
  await page.goto("/register?next=%2Fme%2Fappointments");
  await page.getByLabel("Họ và tên").fill(`So Sánh ${label}`);
  await page.getByLabel("Email").fill(`compare-${Date.now()}-${label}@example.com`);
  await page.getByLabel("Số điện thoại").fill("0912 345 678");
  await page.getByLabel("Ngày sinh").fill("12031994");
  await page.getByText("Nữ", { exact: true }).click();
  await page.getByLabel("Mật khẩu", { exact: true }).fill("matkhau123");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /Tạo tài khoản/ }).click();
  await expect(page.getByRole("heading", { name: "Lịch của tôi" })).toBeVisible();
}

// ---------------------------------------------------------------------------- web
/** Tháng đang hiện trên lịch, dạng YYYY-MM (tiêu đề "Tháng 10/2026"). */
async function shownMonth(page: Page): Promise<string> {
  const heading = page.getByRole("heading", { name: /^Tháng \d{1,2}\/\d{4}$/ });
  const [, month = "", year = ""] =
    /(\d{1,2})\/(\d{4})/.exec((await heading.textContent()) ?? "") ?? [];
  return `${year}-${month.padStart(2, "0")}`;
}

/** Như người dùng: bấm lần lượt các ngày còn khung từ `from` (sang tháng sau khi cần), dừng ở
 *  ngày đầu tiên có khung thỏa `accept`. Trả ngày, giờ đã chọn. */
async function pickDayAndSlot(
  rec: Recorder,
  page: Page,
  from: string,
  accept: (time: string) => boolean,
): Promise<{ day: string; time: string }> {
  const calendar = page.getByRole("group", { name: "Chọn ngày khám" });
  for (let offset = 0; offset < 14; offset += 1) {
    const day = addDays(from, offset);
    await expect(calendar).not.toHaveAttribute("aria-busy", "true"); // đã tải số khung
    while ((await shownMonth(page)) < day.slice(0, 7)) {
      await rec.click(page.getByRole("button", { name: "Tháng sau" }));
      await expect(calendar).not.toHaveAttribute("aria-busy", "true");
    }
    const pattern = new RegExp(`${dayMonth(day)}/\\d{4}, \\d+ khung$`);
    const button = calendar.getByRole("button", { name: pattern });
    if ((await button.count()) === 0) continue; // nghỉ hoặc hết khung
    await rec.click(button);
    await expect(button).toHaveAttribute("aria-pressed", "true");
    const slots = page.getByRole("button", {
      name: new RegExp(`^\\d{2}:\\d{2}, .*${dayMonth(day)}`),
    });
    await expect(slots.first()).toBeVisible();
    for (const slot of await slots.all()) {
      const time = ((await slot.getAttribute("aria-label")) ?? "").slice(0, 5);
      if (accept(time)) {
        await rec.click(slot);
        return { day, time };
      }
    }
  }
  throw new Error("không có khung thỏa yêu cầu trong 14 ngày");
}

type Slot = { day: string; time: string; code?: string };

async function webBook(page: Page, rec: Recorder, task: "T1" | "T2"): Promise<Slot> {
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" }).first();
  await rec.click(nav.getByRole("link", { name: "Đặt lịch", exact: true }));
  await rec.click(page.getByRole("radio", { name: /Da liễu/ }));
  await rec.click(page.getByRole("button", { name: "Chọn Khám da liễu tổng quát" }));
  if (task === "T2") await rec.click(page.getByRole("radio", { name: /Nguyễn Thu Hà/ }));
  await rec.click(page.getByRole("button", { name: "Tiếp tục: chọn ngày giờ" }));
  const slot =
    task === "T1"
      ? await pickDayAndSlot(rec, page, clinicDay(1), () => true)
      : await pickDayAndSlot(rec, page, nextMonday(), (time) => time >= "13:00");
  await rec.click(page.getByRole("button", { name: "Tiếp tục: xem lại" }));
  await rec.click(page.getByRole("button", { name: "Xác nhận đặt lịch" }));
  await expect(page.getByRole("heading", { name: "Đã đặt lịch thành công" })).toBeVisible();
  return slot;
}

/** Mở chi tiết lịch của T2 trong Lịch của tôi: thẻ có giờ bắt đầu của T2 (lịch T1 "bác sĩ bất
 *  kỳ" cũng có thể rơi vào BS. Thu Hà nên không lọc theo tên). */
async function openT2(page: Page, rec: Recorder, slot: Slot) {
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" }).first();
  await rec.click(nav.getByRole("link", { name: "Lịch của tôi", exact: true }));
  const list = page.getByRole("list", { name: "Danh sách lịch hẹn" });
  await rec.click(list.getByRole("link").filter({ hasText: slot.code ?? `${slot.time}–` }));
}

/** Trả khung mới để T4 tìm đúng thẻ. */
async function webReschedule(page: Page, rec: Recorder, slot: Slot): Promise<Slot> {
  await openT2(page, rec, slot);
  const day = slot.day;
  const detail = page.getByRole("region", { name: "Chi tiết lịch hẹn" });
  const code = await detail.getByText(/^LH-\d{6}-[0-9A-Z]{4}$/).textContent();
  await rec.click(detail.getByRole("button", { name: "Đổi lịch" }));
  const dialog = page.getByRole("dialog", { name: "Đổi lịch hẹn" });
  const weekday = WEEKDAY_SHORT[new Date(`${day}T00:00:00Z`).getUTCDay()];
  await rec.click(dialog.getByRole("button", { name: `${weekday} ${dayMonth(day)}`, exact: true }));
  const morning = dialog.getByRole("button", { name: /^(0[7-9]|1[01]):\d{2}, / }).first();
  const time = ((await morning.getAttribute("aria-label")) ?? "").slice(0, 5);
  await rec.click(morning);
  await rec.click(dialog.getByRole("button", { name: "Xác nhận đổi lịch" }));
  await expect(page.getByRole("status").filter({ hasText: "Đã đổi lịch sang" })).toBeVisible();
  return { day, time, code: code ?? undefined };
}

async function webCancel(page: Page, rec: Recorder, slot: Slot) {
  await openT2(page, rec, slot);
  const detail = page.getByRole("region", { name: "Chi tiết lịch hẹn" });
  await rec.click(detail.getByRole("button", { name: "Hủy lịch" }));
  const dialog = page.getByRole("dialog", { name: "Hủy lịch hẹn?" });
  rec.count(); // mở danh sách lý do và chọn một mục: tính một lần bấm
  await dialog.getByRole("combobox").selectOption("Bận việc đột xuất");
  await rec.click(dialog.getByRole("button", { name: "Hủy lịch hẹn" }));
  await expect(page.getByRole("status").filter({ hasText: /^Đã hủy lịch LH-/ })).toBeVisible();
}

// ---------------------------------------------------------------------------- trợ lý
async function agentTask(page: Page, rec: Recorder, task: Task) {
  const panel = page.getByRole("complementary", { name: "Trợ lý đặt lịch" });
  if (!(await panel.isVisible())) await rec.click(page.getByRole("button", { name: "Hỏi trợ lý" }));
  // Khung chat giữ các tin cũ: chỉ tính khung giờ, thẻ, thông báo mới của lượt này.
  const slots = panel.getByRole("button", { name: /^Chọn khung giờ: / });
  const confirm = panel.getByRole("button", { name: CONFIRM[task], exact: true });
  const done = panel.getByRole("status").filter({ hasText: /^Đã (đặt|đổi|hủy) lịch/ });
  const [slotsBefore, doneBefore] = [await slots.count(), await done.count()];

  await rec.type(panel.getByLabel("Tin nhắn cho trợ lý"), AGENT_MESSAGES[task]);
  await rec.click(panel.getByRole("button", { name: "Gửi" }));
  // Trợ lý tạo thẻ ngay, hoặc đưa các khung giờ để người dùng bấm chọn trước.
  await expect
    .poll(async () => (await confirm.count()) > 0 || (await slots.count()) > slotsBefore, {
      timeout: AGENT_TIMEOUT,
    })
    .toBe(true);
  if ((await confirm.count()) === 0) {
    await rec.click(slots.nth(slotsBefore));
    await expect(confirm.first()).toBeVisible({ timeout: AGENT_TIMEOUT });
  }
  await rec.click(confirm.last());
  await expect(done).toHaveCount(doneBefore + 1, { timeout: AGENT_TIMEOUT });
}

// ---------------------------------------------------------------------------- chạy
test("web: đặt, đặt nhiều ràng buộc, đổi, hủy", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "đo trên máy tính");
  test.setTimeout(180_000);
  await register(page, "web");
  page.setDefaultTimeout(15_000); // thiếu phần tử thì báo lỗi tác vụ đó, không treo cả lần đo
  let t2: Slot | undefined;
  await run("T1", "web", async (rec) => {
    await webBook(page, rec, "T1");
  });
  await run("T2", "web", async (rec) => {
    t2 = await webBook(page, rec, "T2");
  });
  if (t2) {
    const booked = t2;
    let moved: Slot | undefined;
    await run("T3", "web", async (rec) => {
      moved = await webReschedule(page, rec, booked);
    });
    await run("T4", "web", (rec) => webCancel(page, rec, moved ?? booked));
  }
  save(testInfo);
  expect(results.filter((r) => r.channel === "web" && !r.success)).toEqual([]);
});

test("trợ lý: cùng bốn tác vụ", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "đo trên máy tính");
  test.skip(!AGENT, "phần trợ lý cần LLM thật: E2E_COMPARE_AGENT=1");
  test.setTimeout(600_000);
  await register(page, "agent");
  for (const task of ["T1", "T2", "T3", "T4"] as const) {
    await run(task, "agent", (rec) => agentTask(page, rec, task));
  }
  save(testInfo);
});
