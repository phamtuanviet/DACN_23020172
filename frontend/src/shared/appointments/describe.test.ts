import { describe, expect, it } from "vitest";

import type { Appointment, HistoryEntry } from "@/shared/api/types";

import { appointmentIcs, channelLabel, describeHistory } from "./describe";

const DOCTOR_A = { id: 7, name: "ThS. BS. Trần Minh" };
const DOCTOR_B = { id: 9, name: "BS. Lê Hoa" };

function entry(overrides: Partial<HistoryEntry>): HistoryEntry {
  return {
    action: "CREATE",
    channel: "WEB",
    actor_role: "PATIENT",
    by_me: true,
    created_at: "2026-10-10T02:24:00Z",
    old: null,
    new: null,
    ...overrides,
  };
}

describe("describeHistory", () => {
  it("người thao tác: bạn, phòng khám, bác sĩ, hệ thống", () => {
    expect(describeHistory(entry({}))).toBe("Bạn đặt lịch");
    expect(describeHistory(entry({ action: "CANCEL", by_me: false, actor_role: "ADMIN" }))).toBe(
      "Phòng khám hủy lịch",
    );
    expect(
      describeHistory(
        entry({
          action: "STATUS_CHANGE",
          by_me: false,
          actor_role: "DOCTOR",
          new: { status: "COMPLETED" },
        }),
      ),
    ).toBe("Bác sĩ cập nhật: Đã khám");
    expect(describeHistory(entry({ action: "FLAG", by_me: false, actor_role: null }))).toBe(
      "Hệ thống đánh dấu cần xử lý",
    );
    const unflag = entry({
      action: "FLAG",
      actor_role: "ADMIN",
      old: { needs_attention: true },
      new: { needs_attention: false },
    });
    expect(describeHistory(unflag)).toBe("Bạn gỡ cờ cần xử lý");
  });

  it("đổi giờ trong ngày chỉ ghi giờ; khác ngày ghi cả ngày; đổi bác sĩ ghi tên", () => {
    const sameDay = entry({
      action: "RESCHEDULE",
      old: { start_at: "2026-10-17T02:20:00Z", doctor: DOCTOR_A },
      new: { start_at: "2026-10-17T01:00:00Z", doctor: DOCTOR_A },
    });
    expect(describeHistory(sameDay)).toBe("Bạn đổi lịch 09:20 → 08:00");

    const otherDay = entry({
      action: "RESCHEDULE",
      old: { start_at: "2026-10-17T01:00:00Z", doctor: DOCTOR_A },
      new: { start_at: "2026-10-19T02:40:00Z", doctor: DOCTOR_B },
    });
    expect(describeHistory(otherDay)).toBe(
      "Bạn đổi lịch T7 17/10 08:00 → T2 19/10 09:40 · ThS. BS. Trần Minh → BS. Lê Hoa",
    );
  });

  it("kênh hiển thị bằng tiếng Việt", () => {
    expect(channelLabel("AGENT")).toBe("Trợ lý");
    expect(channelLabel("ADMIN")).toBe("Phòng khám");
  });
});

describe("appointmentIcs", () => {
  const appointment: Appointment = {
    id: 412,
    code: "LH-261010-7KQ2",
    status: "BOOKED",
    channel: "WEB",
    service: { id: 3, name: "Khám da liễu tổng quát" },
    doctor: DOCTOR_A,
    start_at: "2026-10-17T08:00:00+07:00",
    end_at: "2026-10-17T08:20:00+07:00",
    can_change: true,
    change_until: "2026-10-17T06:00:00+07:00",
  };

  it("giờ đổi sang UTC, dòng kết thúc bằng CRLF, ký tự đặc biệt được thoát", () => {
    const ics = appointmentIcs(appointment, "Phòng khám DACN", "12 Lê Lợi, Q.1");
    expect(ics).toContain("DTSTART:20261017T010000Z\r\n");
    expect(ics).toContain("DTEND:20261017T012000Z\r\n");
    expect(ics).toContain("UID:LH-261010-7KQ2@dacn");
    expect(ics).toContain("LOCATION:12 Lê Lợi\\, Q.1");
    expect(ics.endsWith("END:VCALENDAR\r\n")).toBe(true);
  });

  it("không có địa chỉ thì bỏ dòng LOCATION", () => {
    expect(appointmentIcs(appointment, "Phòng khám DACN", "")).not.toContain("LOCATION");
  });
});
