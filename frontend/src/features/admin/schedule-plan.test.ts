import { describe, expect, it } from "vitest";

import type { AdminAppointment, Shift, TimeOff } from "@/shared/api/types";

import { appliesOn, periodOf, weekPlan } from "./schedule-plan";

const MONDAY = "2026-10-19";

function shift(overrides: Partial<Shift>): Shift {
  return {
    id: 1,
    doctor_id: 7,
    weekday: 1,
    start_time: "07:00:00",
    end_time: "11:30:00",
    valid_from: "2026-09-01",
    valid_to: null,
    ...overrides,
  };
}

function appointment(startAt: string, status: AdminAppointment["status"] = "BOOKED") {
  return { start_at: startAt, status } as AdminAppointment;
}

describe("ca làm", () => {
  it("chia buổi theo giờ bắt đầu", () => {
    expect(periodOf("07:00")).toBe("morning");
    expect(periodOf("13:30")).toBe("afternoon");
    expect(periodOf("17:00")).toBe("evening");
  });

  it("chỉ áp dụng đúng thứ và trong khoảng hiệu lực", () => {
    const limited = shift({ valid_from: "2026-10-20", valid_to: "2026-10-31" });
    expect(appliesOn(shift({}), MONDAY)).toBe(true);
    expect(appliesOn(shift({ weekday: 2 }), MONDAY)).toBe(false);
    expect(appliesOn(limited, MONDAY)).toBe(false);
    expect(appliesOn({ ...limited, weekday: 2 }, "2026-10-20")).toBe(true);
  });
});

describe("weekPlan", () => {
  it("trải ca ra từng ngày và đếm lịch đang hiệu lực trong ca", () => {
    const plan = weekPlan(
      MONDAY,
      [shift({}), shift({ id: 2, start_time: "13:30:00", end_time: "17:00:00" })],
      [],
      [
        appointment("2026-10-19T01:00:00Z"), // 08:00
        appointment("2026-10-19T02:00:00Z", "CANCELLED"),
        appointment("2026-10-19T07:00:00Z", "ARRIVED"), // 14:00
      ],
    );
    expect(plan).toHaveLength(7);
    const monday = plan[0]!;
    expect(monday.blocks.morning.map((b) => [b.start, b.end, b.booked])).toEqual([
      ["07:00", "11:30", 1],
    ]);
    expect(monday.blocks.afternoon[0]?.booked).toBe(1);
    expect(plan[1]!.blocks.morning).toEqual([]);
  });

  it("ngày nghỉ cả ngày và nửa ngày phủ lên ca", () => {
    const allDay = {
      id: 5,
      doctor_id: 7,
      start_at: "2026-10-18T17:00:00Z", // 00:00 thứ Hai
      end_at: "2026-10-19T16:59:00Z", // 23:59 thứ Hai
      reason: "Hội thảo",
    } satisfies TimeOff;
    const morning = {
      ...allDay,
      id: 6,
      start_at: "2026-10-26T01:00:00Z",
      end_at: "2026-10-26T05:00:00Z",
    };
    const [monday] = weekPlan(MONDAY, [shift({})], [allDay, morning], []);
    expect(monday!.timeOffs.map((t) => t.allDay)).toEqual([true]);
    expect(monday!.blocks.morning[0]?.off?.id).toBe(5);

    const [next] = weekPlan("2026-10-26", [shift({})], [morning], []);
    expect(next!.timeOffs[0]).toMatchObject({ allDay: false, start: "08:00", end: "12:00" });
  });
});
