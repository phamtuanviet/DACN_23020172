import { describe, expect, it } from "vitest";

import { errorMessage, fieldErrors, toApiError } from "./errors";

describe("fieldErrors", () => {
  it("lấy tên ô ở cuối loc, giữ lỗi đầu tiên của mỗi ô", () => {
    const error = {
      code: "VALIDATION_ERROR",
      message: "x",
      details: {
        fields: [
          { loc: ["body", "email"], message: "Email không hợp lệ." },
          { loc: ["body", "email"], message: "Lỗi thứ hai" },
          { loc: ["body", "date_of_birth"], message: "Ngày sinh không hợp lệ." },
        ],
      },
    };
    expect(fieldErrors(error)).toEqual({
      email: "Email không hợp lệ.",
      date_of_birth: "Ngày sinh không hợp lệ.",
    });
  });
});

describe("toApiError", () => {
  it("giữ nguyên lỗi đúng dạng của backend", () => {
    expect(toApiError({ code: "EMAIL_TAKEN", message: "m" }).code).toBe("EMAIL_TAKEN");
  });

  it("dựng lỗi chung khi không đọc được thân lỗi", () => {
    expect(toApiError(undefined).code).toBe("INTERNAL_ERROR");
  });
});

describe("errorMessage", () => {
  it("dùng thông báo đã dịch khi biết mã lỗi", () => {
    expect(errorMessage({ code: "SLOT_TAKEN", message: "x" })).toContain("Khung giờ");
  });

  it.each([
    ["BOOKING_WINDOW", "30 ngày"],
    ["SLOT_NOT_OFFERED", "không có trong lịch khám"],
    ["DOCTOR_SERVICE_MISMATCH", "không thực hiện dịch vụ"],
    ["PATIENT_OVERLAP", "trùng giờ"],
    ["MAX_ACTIVE_APPOINTMENTS", "3 lịch"],
  ])("có thông báo tiếng Việt cho lỗi đặt lịch %s", (code, text) => {
    expect(errorMessage({ code, message: "x" })).toContain(text);
  });

  it.each([
    [
      "SHIFT_OVERLAP",
      "Ca này chồng lên ca 08:00–11:30 đã có (hiệu lực 01/10/2026 – không thời hạn).",
    ],
    [
      "CHANGE_DEADLINE_PASSED",
      "Chỉ đổi, hủy trực tuyến trước giờ khám ít nhất 2 giờ. Vui lòng gọi phòng khám theo số 028 3822 0000 để được hỗ trợ.",
    ],
    ["INVALID_TRANSITION", "Lịch hẹn đã hủy nên không đổi, hủy được nữa."],
  ])("giữ message chi tiết của backend cho %s", (code, message) => {
    expect(errorMessage({ code, message })).toBe(message);
  });

  it("dùng message của backend khi chưa có bản dịch", () => {
    expect(errorMessage({ code: "NEW_CODE", message: "Thông báo từ backend" })).toBe(
      "Thông báo từ backend",
    );
  });
});
