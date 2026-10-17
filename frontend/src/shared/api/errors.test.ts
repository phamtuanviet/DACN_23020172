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

  it("giữ message chi tiết của backend cho SHIFT_OVERLAP (nêu ca bị chồng)", () => {
    const message = "Ca này chồng lên ca 08:00–11:30 đã có (hiệu lực 01/10/2026 – không thời hạn).";
    expect(errorMessage({ code: "SHIFT_OVERLAP", message })).toBe(message);
  });

  it("dùng message của backend khi chưa có bản dịch", () => {
    expect(errorMessage({ code: "NEW_CODE", message: "Thông báo từ backend" })).toBe(
      "Thông báo từ backend",
    );
  });
});
