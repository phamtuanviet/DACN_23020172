// Ánh xạ mã lỗi của backend (docs mục 4.7) sang thông báo tiếng Việt cho người dùng.
export type ApiError = { code: string; message: string; details?: Record<string, unknown> };

const MESSAGES: Record<string, string> = {
  SLOT_TAKEN: "Khung giờ vừa được người khác đặt, vui lòng chọn khung khác.",
  CHANGE_DEADLINE_PASSED: "Đã quá thời hạn đổi/hủy trực tuyến, vui lòng gọi phòng khám.",
  MAX_ACTIVE_APPOINTMENTS: "Bạn đã có 3 lịch đang chờ khám.",
  AGENT_UNAVAILABLE: "Trợ lý tạm thời không hoạt động, bạn vẫn đặt lịch được trên trang Đặt lịch.",
  INTERNAL_ERROR: "Hệ thống đang gặp sự cố, vui lòng thử lại sau.",
};

export function errorMessage(error: ApiError): string {
  return MESSAGES[error.code] ?? error.message;
}
