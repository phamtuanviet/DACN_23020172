// Chữ mô tả lịch hẹn: kênh đặt, từng dòng lịch sử thay đổi (FR-APT-05), file .ics thêm vào lịch
// điện thoại. Thuần, không gọi API, để test được.
import type { Appointment, Channel, HistoryEntry } from "@/shared/api/types";
import { clinicDay, formatDayShort, formatTime } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";

const T = TEXT.appointments;

export function channelLabel(channel: Channel): string {
  return T.channels[channel];
}

function actorName(entry: HistoryEntry): string {
  if (entry.by_me) return T.actors.me;
  if (entry.actor_role === null) return T.actors.system;
  return T.actors[entry.actor_role];
}

/** "T7 17/10 08:00", hoặc chỉ "08:00" khi cùng ngày với mốc so sánh. */
function moment(value: string, sameDayAs?: string | null): string {
  const time = formatTime(value);
  if (sameDayAs && clinicDay(sameDayAs) === clinicDay(value)) return time;
  return `${formatDayShort(clinicDay(value))} ${time}`;
}

/** Một dòng lịch sử: "Bạn đổi giờ 09:20 → 08:00", "Bác sĩ cập nhật: Đã khám"… */
export function describeHistory(entry: HistoryEntry): string {
  const who = actorName(entry);
  const { old, new: next } = entry;
  switch (entry.action) {
    case "CREATE":
      return T.changes.create(who);
    case "RESCHEDULE": {
      const parts: string[] = [];
      if (old?.start_at && next?.start_at && old.start_at !== next.start_at) {
        parts.push(
          `${moment(old.start_at, next.start_at)} → ${moment(next.start_at, old.start_at)}`,
        );
      }
      if (old?.doctor && next?.doctor && old.doctor.id !== next.doctor.id) {
        parts.push(`${old.doctor.name} → ${next.doctor.name}`);
      }
      return T.changes.reschedule(who, parts.join(" · "));
    }
    case "CANCEL":
      return T.changes.cancel(who);
    case "STATUS_CHANGE":
      return T.changes.status(who, next?.status ? T.statuses[next.status] : "");
    case "NOTE_UPDATE":
      return T.changes.note(who);
    case "FLAG":
      return next?.needs_attention === false ? T.changes.unflag(who) : T.changes.flag(who);
  }
}

/** Dòng phụ: "12/10/2026 20:05 · Web" */
export function historyChannel(entry: HistoryEntry): string {
  return channelLabel(entry.channel);
}

function icsStamp(value: string): string {
  return new Date(value)
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}/, "");
}

function icsText(value: string): string {
  return value.replace(/[\\;,]/g, (char) => `\\${char}`).replace(/\n/g, "\\n");
}

/** Sự kiện iCalendar (RFC 5545) của một lịch hẹn, giờ UTC để mọi ứng dụng lịch đọc đúng. */
export function appointmentIcs(appointment: Appointment, clinicName: string, address: string) {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//DACN//Dat lich kham//VI",
    "BEGIN:VEVENT",
    `UID:${appointment.code}@dacn`,
    `DTSTAMP:${icsStamp(new Date().toISOString())}`,
    `DTSTART:${icsStamp(appointment.start_at)}`,
    `DTEND:${icsStamp(appointment.end_at)}`,
    `SUMMARY:${icsText(`${appointment.service.name} · ${clinicName}`)}`,
    `DESCRIPTION:${icsText(T.icsDescription(appointment.code, appointment.doctor.name))}`,
    ...(address ? [`LOCATION:${icsText(address)}`] : []),
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return `${lines.join("\r\n")}\r\n`;
}
