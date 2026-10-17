import { describe, expect, it } from "vitest";

import { formatPrice, initials, splitScope, unaccent } from "./format";

describe("format", () => {
  it("giá theo kiểu Việt Nam", () => {
    expect(formatPrice(250_000)).toBe("250.000 ₫");
    expect(formatPrice(0)).toBe("0 ₫");
  });

  it("chữ viết tắt bỏ học hàm, lấy hai từ cuối", () => {
    expect(initials("ThS. BS. Trần Minh")).toBe("TM");
    expect(initials("BS.CKI Nguyễn Thu Hà")).toBe("TH");
    expect(initials("BS. Lê Quốc Bảo")).toBe("QB");
    expect(initials("Lan")).toBe("L");
  });

  it("bỏ dấu tiếng Việt", () => {
    expect(unaccent("Đa Liễu")).toBe("da lieu");
    expect(unaccent("Răng Hàm Mặt")).toBe("rang ham mat");
  });

  it("tách phần Không gồm của phạm vi khám", () => {
    expect(splitScope("Các vấn đề về da. Không gồm thủ thuật thẩm mỹ, laser.")).toEqual({
      included: "Các vấn đề về da.",
      excluded: "thủ thuật thẩm mỹ, laser.",
    });
    expect(splitScope("Chàm, viêm da cơ địa.")).toEqual({
      included: "Chàm, viêm da cơ địa.",
      excluded: null,
    });
  });
});
