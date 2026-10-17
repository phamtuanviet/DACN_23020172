// Đọc trạng thái wizard từ URL (docs mục 9.3). Giá trị sai dạng bị bỏ qua thay vì làm hỏng trang,
// nên đường dẫn cũ hoặc bị sửa tay vẫn mở được ở bước hợp lý gần nhất.
import type { BookingState } from "@/shared/availability/booking-href";
import { isValidDay } from "@/shared/lib/datetime";

type ParamsLike = { get(name: string): string | null };

function positiveInt(value: string | null): number | undefined {
  if (value === null || !/^\d+$/.test(value)) return undefined;
  const number = Number(value);
  return number > 0 ? number : undefined;
}

export function parseBookingParams(params: ParamsLike): BookingState {
  const doctor = params.get("doctor");
  const date = params.get("date");
  const start = params.get("start");
  return {
    q: params.get("q")?.trim().slice(0, 100) || undefined,
    specialty: positiveInt(params.get("specialty")),
    service: positiveInt(params.get("service")),
    doctor: doctor === "any" ? "any" : positiveInt(doctor),
    date: date && isValidDay(date) ? date : undefined,
    start: start && !Number.isNaN(Date.parse(start)) ? start : undefined,
  };
}

/** 0 = chọn dịch vụ, 1 = chọn bác sĩ, 2 = chọn ngày giờ (Sprint 3), 3 = xác nhận. */
export function currentStep(state: BookingState): number {
  if (state.service === undefined) return 0;
  if (state.doctor === undefined) return 1;
  return 2;
}
