import { describe, expect, it } from "vitest";

import { errorMessage } from "./errors";

describe("errorMessage", () => {
  it("dùng thông báo đã dịch khi biết mã lỗi", () => {
    expect(errorMessage({ code: "SLOT_TAKEN", message: "x" })).toContain("Khung giờ");
  });

  it("dùng message của backend khi chưa có bản dịch", () => {
    expect(errorMessage({ code: "NEW_CODE", message: "Thông báo từ backend" })).toBe("Thông báo từ backend");
  });
});
