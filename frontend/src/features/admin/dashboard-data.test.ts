import { describe, expect, it } from "vitest";

import type { DayStats } from "@/shared/api/types";

import {
  niceTicks,
  parsePeriod,
  peakIndex,
  periodRange,
  rateDelta,
  showDayLabel,
} from "./dashboard-data";

function day(date: string, total: number): DayStats {
  return { day: date, total, booked: 0, arrived: 0, completed: total, cancelled: 0, no_show: 0 };
}

describe("dashboard-data", () => {
  it("khoảng thời gian chỉ nhận 7, 14, 30 ngày; mặc định 14", () => {
    expect(parsePeriod("30")).toBe(30);
    expect(parsePeriod("15")).toBe(14);
    expect(parsePeriod(null)).toBe(14);
    expect(periodRange("2026-10-10", 14)).toEqual({ from: "2026-09-27", to: "2026-10-10" });
    expect(periodRange("2026-10-10", 7)).toEqual({ from: "2026-10-04", to: "2026-10-10" });
  });

  it("vạch trục y là số nguyên tròn, sát và cao hơn giá trị lớn nhất", () => {
    expect(niceTicks(86)).toEqual([0, 20, 40, 60, 80, 100]);
    expect(niceTicks(21)).toEqual([0, 5, 10, 15, 20, 25]);
    expect(niceTicks(12)).toEqual([0, 5, 10, 15]);
    expect(niceTicks(10)).toEqual([0, 5, 10, 15]);
    expect(niceTicks(3)).toEqual([0, 1, 2, 3, 4]);
    expect(niceTicks(0)).toEqual([0, 1]);
    for (const max of [1, 7, 19, 40, 99, 101, 349, 1280]) {
      const ticks = niceTicks(max);
      expect(ticks.at(-1)).toBeGreaterThan(max);
      expect(ticks.length).toBeLessThanOrEqual(6);
      expect(ticks.every(Number.isInteger)).toBe(true);
    }
  });

  it("30 cột chỉ ghi nhãn mỗi 5 ngày, luôn có hôm nay", () => {
    const shown = Array.from({ length: 30 }, (_, i) => i).filter((i) => showDayLabel(i, 30));
    expect(shown).toEqual([4, 9, 14, 19, 24, 29]);
    expect(Array.from({ length: 14 }, (_, i) => showDayLabel(i, 14)).every(Boolean)).toBe(true);
  });

  it("cột cao nhất lấy ngày gần nhất khi bằng nhau, không có lịch thì -1", () => {
    expect(peakIndex([day("2026-10-08", 5), day("2026-10-09", 7), day("2026-10-10", 7)])).toBe(2);
    expect(peakIndex([day("2026-10-09", 9), day("2026-10-10", 2)])).toBe(0);
    expect(peakIndex([day("2026-10-10", 0)])).toBe(-1);
  });

  it("chênh lệch tỷ lệ tính bằng điểm phần trăm", () => {
    expect(rateDelta(0.081, 0.093)).toEqual({ direction: "down", points: 1.2 });
    expect(rateDelta(0.2, 0.125)).toEqual({ direction: "up", points: 7.5 });
    expect(rateDelta(0.1, 0.1004)).toEqual({ direction: "same", points: 0 });
    expect(rateDelta(null, 0.1)).toBeNull();
    expect(rateDelta(0.1, null)).toBeNull();
  });
});
