// Ánh xạ mã lỗi của backend (docs mục 4.7) sang thông báo tiếng Việt cho người dùng.
export type FieldIssue = { loc: (string | number)[]; message: string };
export type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown> & {
    fields?: FieldIssue[];
    locked_until?: string;
    request_id?: string;
  };
};

const GENERIC_ERROR = "Hệ thống đang gặp sự cố, vui lòng thử lại sau.";

const MESSAGES: Record<string, string> = {
  UNAUTHENTICATED: "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.",
  FORBIDDEN: "Bạn không có quyền thực hiện thao tác này.",
  RATE_LIMITED: "Bạn thao tác quá nhanh, vui lòng thử lại sau.",
  EMAIL_TAKEN: "Email này đã có tài khoản.",
  VALIDATION_ERROR: "Thông tin chưa hợp lệ, vui lòng kiểm tra lại các ô được đánh dấu.",
  NOT_FOUND: "Không tìm thấy dữ liệu yêu cầu.",
  BOOKING_WINDOW: "Chỉ đặt được lịch cho thời điểm sắp tới, trong vòng 30 ngày.",
  SLOT_NOT_OFFERED:
    "Giờ này không có trong lịch khám của bác sĩ, vui lòng chọn một khung giờ trống.",
  DOCTOR_SERVICE_MISMATCH: "Bác sĩ không thực hiện dịch vụ này hoặc đã ngừng nhận lịch.",
  SLOT_TAKEN: "Khung giờ vừa được người khác đặt, vui lòng chọn khung khác.",
  PATIENT_OVERLAP: "Bạn đã có một lịch hẹn khác trùng giờ này.",
  CHANGE_DEADLINE_PASSED: "Đã quá thời hạn đổi/hủy trực tuyến, vui lòng gọi phòng khám.",
  MAX_ACTIVE_APPOINTMENTS: "Bạn đã có 3 lịch đang chờ khám.",
  AGENT_UNAVAILABLE: "Trợ lý tạm thời không hoạt động, bạn vẫn đặt lịch được trên trang Đặt lịch.",
  INTERNAL_ERROR: GENERIC_ERROR,
};

export function errorMessage(error: ApiError): string {
  return MESSAGES[error.code] ?? error.message;
}

/** Thân lỗi của backend luôn có dạng {code, message, details}; lỗi mạng thì dựng lỗi chung. */
export function toApiError(error: unknown): ApiError {
  if (error && typeof error === "object" && "code" in error && "message" in error)
    return error as ApiError;
  return { code: "INTERNAL_ERROR", message: GENERIC_ERROR };
}

/** Lỗi theo từng ô của VALIDATION_ERROR: {"email": "Email không hợp lệ."}. */
export function fieldErrors(error: ApiError): Record<string, string> {
  const result: Record<string, string> = {};
  for (const issue of error.details?.fields ?? []) {
    const field = issue.loc.at(-1);
    if (typeof field === "string" && !(field in result)) result[field] = issue.message;
  }
  return result;
}
