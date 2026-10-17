import { describe, expect, it } from "vitest";

import {
  addDays,
  clinicDay,
  formatDateTime,
  formatDayFull,
  formatDayLong,
  formatDayShort,
  formatSlot,
  isValidDay,
  weekdayName,
} from "./datetime";

describe("formatDateTime", () => {
  it("hiển thị theo giờ Việt Nam dù đầu vào là UTC", () => {
    expect(formatDateTime("2026-10-17T01:00:00Z")).toMatch(/17\/10\/2026 08:00$/);
  });
});

describe("ngày địa phương", () => {
  it("định dạng thứ như thiết kế", () => {
    expect(formatDayShort("2026-10-16")).toBe("T6 16/10");
    expect(formatDayShort("2026-10-18")).toBe("CN 18/10");
    expect(formatDayLong("2026-10-17")).toBe("Thứ Bảy 17/10");
    expect(formatDayFull("2026-10-18")).toBe("Chủ nhật, 18/10/2026");
    expect(weekdayName(1)).toBe("Thứ Hai");
    expect(weekdayName(7)).toBe("Chủ nhật");
  });

  it("đổi thời điểm sang ngày của phòng khám", () => {
    expect(clinicDay("2026-10-16T18:30:00Z")).toBe("2026-10-17"); // 01:30 sáng 17/10 giờ Việt Nam
    expect(formatSlot("2026-10-16T01:00:00Z")).toBe("T6 16/10, 08:00");
  });

  it("cộng ngày và kiểm tra ngày hợp lệ", () => {
    expect(addDays("2026-10-30", 3)).toBe("2026-11-02");
    expect(isValidDay("2026-02-30")).toBe(false);
    expect(isValidDay("abc")).toBe(false);
    expect(isValidDay("2026-10-17")).toBe(true);
  });
});
