// Trạng thái wizard đặt lịch nằm trên URL (docs mục 9.3): nút Quay lại của trình duyệt luôn đúng
// và các trang công khai dẫn thẳng vào đúng bước với lựa chọn có sẵn.

export type BookingState = {
  specialty?: number;
  service?: number;
  /** "any" = bác sĩ bất kỳ */
  doctor?: number | "any";
  date?: string;
  start?: string;
  q?: string;
};

export function bookingHref(state: BookingState): string {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.specialty !== undefined) params.set("specialty", String(state.specialty));
  if (state.service !== undefined) params.set("service", String(state.service));
  if (state.doctor !== undefined) params.set("doctor", String(state.doctor));
  if (state.date) params.set("date", state.date);
  if (state.start) params.set("start", state.start);
  const query = params.toString();
  return query ? `/booking?${query}` : "/booking";
}
