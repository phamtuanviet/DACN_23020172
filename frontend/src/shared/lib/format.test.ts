import { describe, expect, it } from "vitest";

import {
  formatCount,
  formatPercent,
  formatPhone,
  formatPrice,
  formatRating,
  initials,
  splitScope,
  unaccent,
} from "./format";

describe("format", () => {
  it("số điện thoại tách nhóm 4-3-3", () => {
    expect(formatPhone("0912345678")).toBe("0912 345 678");
    expect(formatPhone(null)).toBe("");
    expect(formatPhone("+8491234")).toBe("+8491234");
  });

  it("giá theo kiểu Việt Nam", () => {
    expect(formatPrice(250_000)).toBe("250.000 ₫");
    expect(formatPrice(0)).toBe("0 ₫");
  });

  it("điểm, tỷ lệ, số đếm dùng dấu phẩy thập phân và dấu chấm hàng nghìn", () => {
    expect(formatRating(4.8)).toBe("4,8");
    expect(formatRating(5)).toBe("5,0");
    expect(formatPercent(0.0812)).toBe("8,1%");
    expect(formatPercent(0)).toBe("0,0%");
    expect(formatCount(1284)).toBe("1.284");
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
