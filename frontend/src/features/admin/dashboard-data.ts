// Phần tính toán thuần của dashboard (AD-dashboard): khoảng ngày, vạch trục, nhãn trục ngày, chênh
// lệch tỷ lệ so với kỳ trước. Tách khỏi component để test không cần trình duyệt.
import type { DayStats } from "@/shared/api/types";
import { addDays } from "@/shared/lib/datetime";

export const PERIODS = [7, 14, 30] as const;
export type Period = (typeof PERIODS)[number];
export const DEFAULT_PERIOD: Period = 14;

export function parsePeriod(value: string | null): Period {
  return PERIODS.find((period) => String(period) === value) ?? DEFAULT_PERIOD;
}

/** `days` ngày tính đến hết hôm nay, dạng "YYYY-MM-DD" như date_from, date_to của API. */
export function periodRange(today: string, days: number): { from: string; to: string } {
  return { from: addDays(today, 1 - days), to: today };
}

/** Vạch trục y là số nguyên tròn (bước 1, 2, 5, 10, 20, 25, 50…), tối đa 5 khoảng; vạch cuối
 *  luôn cao hơn giá trị lớn nhất để cột cao nhất còn chỗ ghi số. */
export function niceTicks(max: number, maxIntervals = 5): number[] {
  for (let magnitude = 1; ; magnitude *= 10) {
    for (const base of [1, 2, 2.5, 5]) {
      const step = base * magnitude;
      const intervals = Math.floor(Math.max(max, 0) / step) + 1;
      if (Number.isInteger(step) && intervals <= maxIntervals) {
        return Array.from({ length: intervals + 1 }, (_, i) => i * step);
      }
    }
  }
}

/** Cứ bao nhiêu cột thì ghi một nhãn ngày, để 30 cột trên điện thoại không chồng chữ. Nhãn luôn
 *  rơi vào ngày cuối (hôm nay) rồi lùi dần. */
export function labelEvery(count: number): number {
  return count <= 14 ? 1 : 5;
}

export function showDayLabel(index: number, count: number): boolean {
  return (count - 1 - index) % labelEvery(count) === 0;
}

/** Cột cao nhất (ngày gần nhất nếu bằng nhau) để ghi số trực tiếp; không có lịch thì -1. */
export function peakIndex(days: DayStats[]): number {
  let best = -1;
  days.forEach((day, index) => {
    if (day.total > 0 && (best < 0 || day.total >= (days[best]?.total ?? 0))) best = index;
  });
  return best;
}

export type Delta = { direction: "up" | "down" | "same"; points: number };

/** Chênh lệch hai tỷ lệ (0–1) tính bằng điểm phần trăm, làm tròn một chữ số. */
export function rateDelta(current: number | null, previous: number | null): Delta | null {
  if (current === null || previous === null) return null;
  const points = Math.round(Math.abs(current - previous) * 1000) / 10;
  if (points === 0) return { direction: "same", points: 0 };
  return { direction: current > previous ? "up" : "down", points };
}
