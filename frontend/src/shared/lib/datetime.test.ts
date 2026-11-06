import { describe, expect, it } from "vitest";

import {
  addDays,
  addMonths,
  clinicDateTime,
  clinicDay,
  dayBadge,
  daysBetween,
  formatDateTime,
  formatDayFull,
  formatDayLong,
  formatDayShort,
  formatMonth,
  formatSlot,
  formatStamp,
  formatTimeRange,
  formatWeekRange,
  isoWeekday,
  isValidDay,
  mondayOf,
  monthGrid,
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

describe("lịch tháng và thẻ lịch hẹn", () => {
  it("lưới tháng bắt đầu từ Thứ Hai", () => {
    const { leading, days } = monthGrid("2026-10"); // 01/10/2026 là Thứ Năm
    expect(leading).toBe(3);
    expect(days).toHaveLength(31);
    expect(days.at(-1)).toBe("2026-10-31");
    expect(monthGrid("2026-02").days).toHaveLength(28);
  });

  it("chuyển tháng qua năm và đếm ngày", () => {
    expect(addMonths("2026-12", 1)).toBe("2027-01");
    expect(addMonths("2026-01", -1)).toBe("2025-12");
    expect(formatMonth("2026-10")).toBe("Tháng 10/2026");
    expect(daysBetween("2026-10-30", "2026-11-02")).toBe(3);
  });

  it("thẻ lịch hẹn theo giờ Việt Nam", () => {
    // 17:30 UTC ngày 16/10 là 00:30 ngày 17/10 ở Việt Nam
    expect(dayBadge("2026-10-16T17:30:00Z")).toEqual({ weekday: "T7", day: "17", month: "Th10" });
    expect(formatTimeRange("2026-10-17T01:00:00Z", "2026-10-17T01:20:00Z")).toBe("08:00–08:20");
    expect(formatStamp("2026-10-12T13:05:00Z")).toBe("12/10/2026 20:05");
  });
});

describe("tuần làm việc", () => {
  it("Thứ Hai của tuần và số thứ theo ca làm", () => {
    expect(isoWeekday("2026-10-18")).toBe(7); // Chủ nhật
    expect(isoWeekday("2026-10-19")).toBe(1);
    expect(mondayOf("2026-10-18")).toBe("2026-10-12");
    expect(mondayOf("2026-10-19")).toBe("2026-10-19");
  });

  it("khoảng tuần ngắn gọn, ghi đủ tháng khi sang tháng mới", () => {
    expect(formatWeekRange("2026-10-19")).toBe("19–25/10/2026");
    expect(formatWeekRange("2026-09-28")).toBe("28/09–04/10/2026");
  });

  it("giờ phòng khám đổi sang UTC bất kể múi giờ của máy", () => {
    expect(clinicDateTime("2026-10-21", "07:00")).toBe("2026-10-21T00:00:00.000Z");
  });
});
