import { describe, expect, it } from "vitest";

import { openStatus, summarizeWorkingHours } from "./schedule-text";

const shift = (weekday: number, start: string, end: string) => ({
  weekday,
  start_time: `${start}:00`,
  end_time: `${end}:00`,
});

describe("summarizeWorkingHours", () => {
  it("gộp các thứ liên tiếp có cùng giờ làm", () => {
    const hours = [1, 2, 3, 4, 5].flatMap((d) => [
      shift(d, "13:30", "17:00"),
      shift(d, "08:00", "11:30"),
    ]);
    hours.push(shift(6, "08:00", "11:30"));
    expect(summarizeWorkingHours(hours)).toEqual([
      { days: "Thứ Hai đến Thứ Sáu", hours: "08:00–11:30 và 13:30–17:00" },
      { days: "Thứ Bảy", hours: "08:00–11:30" },
    ]);
  });

  it("liệt kê từng thứ khi không liên tiếp", () => {
    const hours = [
      shift(1, "08:00", "11:30"),
      shift(3, "08:00", "11:30"),
      shift(7, "08:00", "11:30"),
    ];
    expect(summarizeWorkingHours(hours)).toEqual([
      { days: "Thứ Hai, Thứ Tư, Chủ nhật", hours: "08:00–11:30" },
    ]);
  });

  it("không có ca thì trả rỗng", () => {
    expect(summarizeWorkingHours([])).toEqual([]);
  });
});

describe("openStatus", () => {
  it("theo giờ Việt Nam, kể cả khi máy chạy giờ UTC", () => {
    // Thứ Sáu 16/10/2026 09:00 giờ Việt Nam = 02:00 UTC
    expect(openStatus(new Date("2026-10-16T02:00:00Z"))).toEqual({ open: true, until: "17:00" });
    // Thứ Bảy 12:00: buổi sáng đã đóng cửa
    expect(openStatus(new Date("2026-10-17T05:00:00Z"))).toEqual({ open: false });
    // Chủ nhật nghỉ
    expect(openStatus(new Date("2026-10-18T02:00:00Z"))).toEqual({ open: false });
  });
});
