// Tính toán thuần cho lịch khám của bác sĩ (D-day, D-week): đếm theo trạng thái, nút đổi trạng
// thái hợp lệ, lưới 30 phút của tuần. Không gọi API, để test được; giờ luôn theo giờ phòng khám.
import type {
  AppointmentStatus,
  ScheduleAppointment,
  TimeBlock,
  TimeOffBlock,
} from "@/shared/api/types";
import { addDays, clinicDay, formatTime } from "@/shared/lib/datetime";

import type { VisitStatus } from "./queries";

export type DaySummary = {
  total: number;
  completed: number;
  inProgress: number;
  waiting: number;
  noShow: number;
  cancelled: number;
};

export function summarize(items: ScheduleAppointment[]): DaySummary {
  const count = (status: AppointmentStatus) => items.filter((a) => a.status === status).length;
  return {
    total: items.length,
    completed: count("COMPLETED"),
    inProgress: count("ARRIVED"),
    waiting: count("BOOKED"),
    noShow: count("NO_SHOW"),
    cancelled: count("CANCELLED"),
  };
}

/** Nút đổi trạng thái bác sĩ bấm được ngay (docs mục 5.5): chỉ lịch hôm nay; Vắng mặt khi đã tới
 *  giờ khám. Backend vẫn kiểm tra lại mọi điều kiện. */
export function visitActions(
  appointment: Pick<ScheduleAppointment, "status" | "start_at">,
  now: Date,
): VisitStatus[] {
  if (clinicDay(appointment.start_at) !== clinicDay(now)) return [];
  if (appointment.status === "ARRIVED") return ["COMPLETED"];
  if (appointment.status !== "BOOKED") return [];
  return Date.parse(appointment.start_at) <= now.getTime() ? ["NO_SHOW", "ARRIVED"] : ["ARRIVED"];
}

/** "Nguyễn Thị Lan" → "Lan": tên gọi trên ô lưới tuần. */
export function givenName(fullName: string): string {
  return fullName.trim().split(/\s+/).at(-1) ?? fullName;
}

const SLOT_MINUTES = 30;

function minutes(time: string): number {
  const [hours = 0, mins = 0] = time.split(":").map(Number);
  return hours * 60 + mins;
}

function label(total: number): string {
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/** Khối giờ (ca làm, ngày nghỉ) phủ ô bắt đầu lúc `slot` của ngày `day`; khối kéo qua nhiều ngày
 *  được cắt theo từng ngày. */
function covering<B extends { start_at: string; end_at: string }>(
  blocks: B[],
  day: string,
  slot: string,
): B | undefined {
  return blocks.find((block) => {
    const startDay = clinicDay(block.start_at);
    const endDay = clinicDay(block.end_at);
    if (day < startDay || day > endDay) return false;
    const start = startDay < day ? "00:00" : formatTime(block.start_at);
    const end = endDay > day ? "24:00" : formatTime(block.end_at);
    return start <= slot && slot < end;
  });
}

export type WeekCell = {
  appointments: ScheduleAppointment[];
  working: boolean;
  off: TimeOffBlock | null;
};

export type WeekGrid = { days: string[]; rows: string[]; cells: WeekCell[][] };

/** Lưới tuần: hàng 30 phút từ giờ làm hoặc lịch sớm nhất tới muộn nhất (mặc định 07:00–17:00),
 *  cột Thứ Hai → Chủ nhật; lịch đã hủy không hiện. */
export function weekGrid(
  monday: string,
  appointments: ScheduleAppointment[],
  work: TimeBlock[],
  timeOffs: TimeOffBlock[],
): WeekGrid {
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  const shown = appointments.filter((a) => a.status !== "CANCELLED");
  const starts = [...work.map((w) => w.start_at), ...shown.map((a) => a.start_at)].map((v) =>
    minutes(formatTime(v)),
  );
  const ends = [...work.map((w) => w.end_at), ...shown.map((a) => a.end_at)].map((v) =>
    minutes(formatTime(v)),
  );
  const first = Math.floor(Math.min(7 * 60, ...starts) / SLOT_MINUTES) * SLOT_MINUTES;
  const last = Math.ceil(Math.max(17 * 60, ...ends) / SLOT_MINUTES) * SLOT_MINUTES;
  const rows: string[] = [];
  for (let t = first; t < last; t += SLOT_MINUTES) rows.push(label(t));

  const cells = rows.map((slot) =>
    days.map((day) => ({
      appointments: shown.filter((a) => {
        if (clinicDay(a.start_at) !== day) return false;
        const start = minutes(formatTime(a.start_at));
        return start >= minutes(slot) && start < minutes(slot) + SLOT_MINUTES;
      }),
      working: covering(work, day, slot) !== undefined,
      off: covering(timeOffs, day, slot) ?? null,
    })),
  );
  return { days, rows, cells };
}
