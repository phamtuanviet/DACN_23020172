import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

// Sprint 5: khu vực quản trị (AC-07, AC-08; FR-ADM-01..04) và bác sĩ (AC-09, AC-17) trên giao diện
// thật. Dùng tài khoản quản trị, bác sĩ của seed: mật khẩu demo chỉ có ở development, staging thì
// truyền E2E_DEMO_PASSWORD. Chỉ chạy project máy tính vì đăng nhập giới hạn 10 lần/phút/IP; bố cục
// 360 px kiểm bằng setViewportSize ngay trong test. Bệnh nhân được tạo qua API bằng `request`
// (ngữ cảnh riêng), để cookie phiên của bệnh nhân không đè lên phiên quản trị, bác sĩ trên trang.

const PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "Demo12345";
const WEEKDAYS = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];

const DESKTOP_ONLY = "đăng nhập giới hạn 10 lần/phút/IP: chạy trên máy tính, tự thu về 360 px";

/** Ngày theo giờ Việt Nam, dạng YYYY-MM-DD, cách hôm nay `offset` ngày. */
function clinicDay(offset = 0): string {
  const moment = new Date(Date.now() + offset * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(moment);
}

function weekdayOf(day: string): string {
  return WEEKDAYS[new Date(`${day}T00:00:00Z`).getUTCDay()] ?? "";
}

async function login(page: Page, email: string, next: string) {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page).toHaveURL((url) => url.pathname === next.split("?")[0]);
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

type Patient = { name: string; headers: Record<string, string> };
let shared: Patient | undefined;

/** Một bệnh nhân cho cả hai test của file: /auth/register giới hạn 5 lần/phút/IP. Lịch của test
 *  trước đã hủy hoặc đã khám nên không vướng giới hạn 3 lịch đang chờ. */
async function patientFor(request: APIRequestContext): Promise<Patient> {
  shared ??= await registerPatient(request, String(Date.now()));
  return shared;
}

async function registerPatient(request: APIRequestContext, stamp: string): Promise<Patient> {
  const name = `Khách Thử ${stamp}`;
  const response = await request.post("/api/v1/auth/register", {
    data: {
      full_name: name,
      email: `e2e-${stamp}-benh-nhan@example.com`,
      phone: "0912345678",
      date_of_birth: "1994-03-12",
      gender: "FEMALE",
      password: "matkhau123",
      privacy_consent: true,
    },
  });
  expect(response.status()).toBe(201);
  const { access_token } = (await response.json()) as { access_token: string };
  return { name, headers: { Authorization: `Bearer ${access_token}` } };
}

type Slot = { start_at: string };

async function slotsOf(
  request: APIRequestContext,
  serviceId: number,
  doctorId: number,
  day: string,
): Promise<Slot[]> {
  const response = await request.get("/api/v1/availability", {
    params: { service_id: serviceId, doctor_id: doctorId, date_from: day, date_to: day },
  });
  expect(response.ok()).toBe(true);
  const body = (await response.json()) as { days: { slots: Slot[] }[] };
  return body.days[0]?.slots ?? [];
}

async function book(
  request: APIRequestContext,
  patient: Patient,
  serviceId: number,
  doctorId: number,
  startAt: string,
): Promise<number> {
  const response = await request.post("/api/v1/appointments", {
    headers: patient.headers,
    data: { service_id: serviceId, doctor_id: doctorId, start_at: startAt },
  });
  expect(response.status()).toBe(201);
  return ((await response.json()) as { id: number }).id;
}

test("quản trị tạo danh mục, bác sĩ, ca làm; bệnh nhân đặt được ngay; ngày nghỉ đưa lịch vào hàng chờ", async ({
  page,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", DESKTOP_ONLY);
  const stamp = String(Date.now());
  const specialty = `E2E ${stamp}`;
  const service = `Khám E2E ${stamp}`;
  const doctor = `Kiểm Thử ${stamp}`;
  const tomorrow = clinicDay(1);
  await login(page, "admin@demo.local", "/admin/catalog");

  // AC-07: chuyên khoa, dịch vụ có thời lượng (UC13)
  await page.getByRole("tab", { name: /Chuyên khoa/ }).click();
  await page.getByRole("button", { name: "Thêm chuyên khoa" }).click();
  await page
    .getByRole("complementary", { name: "Chuyên khoa mới" })
    .getByLabel("Tên chuyên khoa")
    .fill(specialty);
  await page.getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByText(`Đã lưu ${specialty}`)).toBeVisible();

  await page.getByRole("tab", { name: /Dịch vụ/ }).click();
  await page.getByRole("button", { name: "Thêm dịch vụ" }).click();
  const serviceForm = page.getByRole("complementary", { name: "Dịch vụ mới" });
  await serviceForm.getByLabel("Tên dịch vụ").fill(service);
  await serviceForm.getByLabel("Chuyên khoa").selectOption({ label: specialty });
  await serviceForm
    .getByLabel("Mô tả phạm vi khám")
    .fill("Khám thử cho kiểm thử tự động, không khám thật.");
  await serviceForm.getByLabel("Thời lượng").selectOption({ label: "30 phút" });
  await serviceForm.getByLabel("Giá tham khảo (₫)").fill("100000");
  await page.getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByText(`Đã lưu ${service}`)).toBeVisible();

  // Tài khoản bác sĩ do quản trị tạo, gán chuyên khoa và dịch vụ (UC14, FR-AUTH-05)
  await page.goto("/admin/doctors");
  await page.getByRole("button", { name: "Thêm bác sĩ" }).click();
  const doctorForm = page.getByRole("complementary", { name: "Bác sĩ mới" });
  await doctorForm.getByLabel("Họ và tên").fill(doctor);
  await doctorForm.getByLabel("Email đăng nhập").fill(`e2e-${stamp}-bac-si@example.com`);
  await doctorForm.getByLabel("Mật khẩu ban đầu").fill("Matkhau123");
  await doctorForm.getByLabel("Chuyên khoa").selectOption({ label: specialty });
  await doctorForm.getByRole("checkbox", { name: service }).check();
  await page.getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByText(`Đã tạo tài khoản BS. ${doctor}`)).toBeVisible();

  // Ca làm lặp hằng tuần vào thứ của ngày mai (UC15)
  await page
    .getByRole("row", { name: new RegExp(doctor) })
    .getByRole("link", { name: "Ca làm" })
    .click();
  await expect(page).toHaveURL(/\/admin\/schedules\/\d+/);
  const doctorId = Number(/\/admin\/schedules\/(\d+)/.exec(page.url())?.[1]);
  await page.getByRole("button", { name: "Thêm ca làm" }).click();
  const shiftForm = page.getByRole("complementary", { name: "Thêm ca làm" });
  await shiftForm.getByLabel("Thứ trong tuần").selectOption({ label: weekdayOf(tomorrow) });
  await shiftForm.getByLabel("Giờ bắt đầu").fill("08:00");
  await shiftForm.getByLabel("Giờ kết thúc").fill("09:30");
  await page.getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByText("Đã lưu ca làm")).toBeVisible();

  // Khung trống của bác sĩ mới xuất hiện ngay cho bệnh nhân, đặt được luôn
  const profile = await request.get(`/api/v1/doctors/${doctorId}`);
  const serviceId = ((await profile.json()) as { services: { id: number }[] }).services[0]!.id;
  const slots = await slotsOf(request, serviceId, doctorId, tomorrow);
  expect(slots.length).toBe(3); // 08:00, 08:30, 09:00
  const patient = await patientFor(request);
  await book(request, patient, serviceId, doctorId, slots[0]!.start_at);

  // AC-08: thêm ngày nghỉ trùng lịch đã đặt thì thấy lịch bị ảnh hưởng trước khi lưu (BR-10)
  await page.getByRole("button", { name: "Thêm ngày nghỉ" }).click();
  const timeOffForm = page.getByRole("complementary", { name: "Thêm ngày nghỉ" });
  await timeOffForm.getByLabel("Từ, ngày").fill(tomorrow);
  await timeOffForm.getByLabel("Đến, ngày").fill(tomorrow);
  await timeOffForm.getByLabel("Lý do").fill("Kiểm thử ngày nghỉ");
  await page.getByRole("button", { name: "Xem trước lịch bị ảnh hưởng" }).click();
  await expect(page.getByText("1 lịch hẹn bị ảnh hưởng")).toBeVisible();
  await expect(page.getByRole("status").getByText(new RegExp(patient.name))).toBeVisible();
  await page.getByRole("button", { name: "Lưu và gắn cờ 1 lịch" }).click();
  await expect(page.getByText("Đã lưu ngày nghỉ, gắn cờ 1 lịch cần xử lý")).toBeVisible();

  // Hàng chờ: lịch bị gắn cờ, quản trị hủy kèm lý do (FR-ADM-04); hệ thống không tự hủy
  await page.goto("/admin/appointments?tab=queue");
  const item = page.getByRole("listitem").filter({ hasText: patient.name });
  await expect(item.getByText(/Bác sĩ nghỉ/)).toBeVisible();
  await item.getByRole("button", { name: "Hủy" }).click();
  await page.getByLabel(/Lý do/).selectOption({ label: "Bác sĩ nghỉ" });
  await page.getByRole("button", { name: "Hủy lịch hẹn" }).click();
  await expect(page.getByText(/^Đã hủy lịch LH-/)).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: patient.name })).toHaveCount(0);

  // Dọn dữ liệu thử: ẩn chuyên khoa thì dịch vụ và bác sĩ cũng ẩn khỏi trang công khai
  await page.goto("/admin/catalog?tab=specialties");
  await page.getByRole("button", { name: specialty, exact: true }).click();
  await page
    .getByRole("complementary", { name: "Sửa chuyên khoa" })
    .getByRole("checkbox", { name: /Hiển thị cho bệnh nhân/ })
    .uncheck();
  await page.getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByText(`Đã lưu ${specialty}`)).toBeVisible();
  // …và khóa tài khoản bác sĩ thử (lịch của bác sĩ này đã hủy ở trên)
  await page.goto("/admin/doctors");
  await page.getByRole("button", { name: `BS. ${doctor}`, exact: true }).click();
  await page.getByRole("checkbox", { name: /Khóa tài khoản/ }).check();
  await page.getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page.getByText(`Đã lưu BS. ${doctor}`)).toBeVisible();

  // Điện thoại 360 px: danh sách lịch hẹn dạng thẻ, không cuộn ngang
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/admin/appointments");
  await expect(page.getByText(/^Hiển thị \d+–\d+ trong \d+ lịch hẹn$/)).toBeVisible();
  await noHorizontalScroll(page);
});

test("bác sĩ xem lịch ngày, tuần; đánh dấu đã đến, ghi chú, đã khám; bệnh nhân thấy ngay", async ({
  page,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", DESKTOP_ONLY);
  const today = clinicDay(0);
  const search = await request.get("/api/v1/doctors", { params: { q: "Trần Minh" } });
  const minh = ((await search.json()) as { id: number; services: { id: number }[] }[])[0]!;
  const serviceId = minh.services[0]!.id;
  const slots = await slotsOf(request, serviceId, minh.id, today);
  test.skip(slots.length === 0, "hôm nay bác sĩ không còn khung trống để dựng lịch thử");
  const patient = await patientFor(request);
  const appointmentId = await book(request, patient, serviceId, minh.id, slots.at(-1)!.start_at);

  // AC-09: bác sĩ chỉ thấy lịch của mình, theo ngày (mặc định hôm nay)
  await login(page, "minh.tran@demo.local", "/doctor/schedule");
  const row = page.getByRole("listitem").filter({ hasText: patient.name });
  await expect(row).toBeVisible();
  await expect(page.getByText("Ca làm hôm nay")).toBeVisible();

  // AC-17: đã đến → ghi chú → đã khám
  await row.getByRole("button", { name: "Đã đến" }).click();
  await expect(row.getByText("Đang khám")).toBeVisible();
  await row.getByRole("link", { name: "Ghi chú" }).click();
  await expect(page).toHaveURL(new RegExp(`/doctor/appointments/${appointmentId}$`));
  const note = "Viêm da tiếp xúc nhẹ. Bôi thuốc theo đơn 7 ngày.";
  await page.getByRole("textbox", { name: "Ghi chú sau khám" }).fill(note);
  await page.getByRole("button", { name: "Lưu ghi chú" }).click();
  await expect(page.getByText("Đã lưu ghi chú")).toBeVisible();
  await page.getByRole("button", { name: "Đánh dấu đã khám" }).click();
  await expect(page.getByText("Lịch đã kết thúc, không đổi trạng thái được nữa.")).toBeVisible();

  // Bệnh nhân thấy trạng thái mới và ghi chú (cùng API trang Lịch của tôi dùng)
  const seen = await request.get(`/api/v1/appointments/${appointmentId}`, {
    headers: patient.headers,
  });
  expect(await seen.json()).toMatchObject({ status: "COMPLETED", doctor_note: note });

  // Xem theo tuần, rồi điện thoại 360 px luôn xem theo ngày, không cuộn ngang
  await page.goto("/doctor/schedule?view=week");
  await expect(page.getByText("Mỗi ô là 30 phút", { exact: false })).toBeVisible();
  const givenName = patient.name.split(" ").at(-1)!; // ô lưới tuần ghi "giờ + tên gọi"
  await expect(page.getByRole("link", { name: new RegExp(givenName) }).first()).toBeVisible();
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/doctor/schedule");
  await expect(page.getByRole("listitem").filter({ hasText: patient.name })).toBeVisible();
  await noHorizontalScroll(page);

  // Bấm tên ở cuối menu mở trang Tài khoản: email đăng nhập và đổi mật khẩu ban đầu
  await page.getByRole("button", { name: "Mở menu" }).click();
  await page.getByRole("link", { name: /Trần Minh/ }).click();
  await expect(page).toHaveURL(/\/doctor\/account$/);
  await expect(page.getByText("minh.tran@demo.local")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Đổi mật khẩu" })).toBeVisible();
  await noHorizontalScroll(page);

  // Đăng xuất từ ngăn kéo menu trên điện thoại; mở lại khu vực bác sĩ thì về trang đăng nhập
  await page.getByRole("button", { name: "Mở menu" }).click();
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/doctor/schedule");
  await expect(page).toHaveURL(/\/login\?next=%2Fdoctor%2Fschedule$/);
});
