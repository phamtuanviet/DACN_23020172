import { describe, expect, it } from "vitest";

import type { ScheduleAppointment } from "@/shared/api/types";

import { givenName, summarize, visitActions, weekGrid } from "./plan";

function appointment(
  id: number,
  startAt: string,
  status: ScheduleAppointment["status"] = "BOOKED",
  minutes = 20,
): ScheduleAppointment {
  const end = new Date(Date.parse(startAt) + minutes * 60_000).toISOString();
  return {
    id,
    code: `LH-${id}`,
    status,
    channel: "WEB",
    service: { id: 1, name: "Khám da liễu tổng quát" },
    start_at: startAt,
    end_at: end,
    patient: { id: id + 100, name: "Nguyễn Thị Lan", age: 32 },
    reason: null,
    has_note: false,
  };
}

// Thứ Bảy 17/10/2026, giờ Việt Nam = UTC+7
const AT_0800 = "2026-10-17T01:00:00Z";
const NOW_0815 = new Date("2026-10-17T01:15:00Z");

describe("summarize", () => {
  it("đếm theo trạng thái như thanh tóm tắt D-day", () => {
    const items = [
      appointment(1, AT_0800, "COMPLETED"),
      appointment(2, AT_0800, "ARRIVED"),
      appointment(3, AT_0800),
      appointment(4, AT_0800, "NO_SHOW"),
      appointment(5, AT_0800, "CANCELLED"),
    ];
    expect(summarize(items)).toEqual({
      total: 5,
      completed: 1,
      inProgress: 1,
      waiting: 1,
      noShow: 1,
      cancelled: 1,
    });
  });
});

describe("visitActions", () => {
  it("Vắng mặt chỉ khi đã tới giờ khám; đã đến thì chỉ còn Đã khám", () => {
    expect(visitActions(appointment(1, AT_0800), NOW_0815)).toEqual(["NO_SHOW", "ARRIVED"]);
    expect(visitActions(appointment(1, "2026-10-17T02:00:00Z"), NOW_0815)).toEqual(["ARRIVED"]);
    expect(visitActions(appointment(1, AT_0800, "ARRIVED"), NOW_0815)).toEqual(["COMPLETED"]);
    expect(visitActions(appointment(1, AT_0800, "COMPLETED"), NOW_0815)).toEqual([]);
  });

  it("không cập nhật lịch của ngày khác", () => {
    expect(visitActions(appointment(1, "2026-10-18T01:00:00Z"), NOW_0815)).toEqual([]);
    expect(visitActions(appointment(1, "2026-10-16T01:00:00Z"), NOW_0815)).toEqual([]);
  });
});

describe("weekGrid", () => {
  it("hàng 30 phút, lịch vào đúng ô, ô ngoài ca và ngày nghỉ", () => {
    const grid = weekGrid(
      "2026-10-12",
      [
        appointment(1, "2026-10-12T00:00:00Z"), // T2 07:00
        appointment(2, "2026-10-12T00:20:00Z"), // T2 07:20 cùng ô 07:00
        appointment(3, "2026-10-13T01:00:00Z", "CANCELLED"),
      ],
      [{ start_at: "2026-10-12T00:00:00Z", end_at: "2026-10-12T04:30:00Z" }], // T2 07:00–11:30
      [{ start_at: "2026-10-15T01:00:00Z", end_at: "2026-10-15T03:00:00Z", reason: "Họp" }],
    );
    expect(grid.rows[0]).toBe("07:00");
    expect(grid.rows.at(-1)).toBe("16:30");
    expect(grid.days[0]).toBe("2026-10-12");
    const first = grid.cells[0]!;
    expect(first[0]!.appointments.map((a) => a.id)).toEqual([1, 2]);
    expect(first[0]!.working).toBe(true);
    expect(first[1]!.working).toBe(false);
    expect(grid.cells.flat().some((cell) => cell.appointments.some((a) => a.id === 3))).toBe(false);
    const thursday0800 = grid.cells[grid.rows.indexOf("08:00")]![3]!;
    expect(thursday0800.off?.reason).toBe("Họp");
  });
});

describe("givenName", () => {
  it("lấy tên gọi", () => {
    expect(givenName("Nguyễn Thị Lan")).toBe("Lan");
    expect(givenName(" Hùng ")).toBe("Hùng");
  });
});
