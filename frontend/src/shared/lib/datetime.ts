// Mọi ngày giờ hiển thị theo giờ phòng khám, bất kể múi giờ máy người dùng (docs mục 7.6).
import { vi } from "date-fns/locale";
import { formatInTimeZone } from "date-fns-tz";

export const CLINIC_TZ = "Asia/Ho_Chi_Minh";

export function formatDateTime(value: Date | string): string {
  return formatInTimeZone(value, CLINIC_TZ, "EEEE, dd/MM/yyyy HH:mm", { locale: vi });
}

export function formatTime(value: Date | string): string {
  return formatInTimeZone(value, CLINIC_TZ, "HH:mm", { locale: vi });
}
