import { describe, expect, it } from "vitest";

import {
  formatBirthDateInput,
  normalizePhone,
  parseBirthDate,
  passwordStrength,
  registerSchema,
} from "./validation";

const TODAY = new Date(2026, 9, 16); // 16/10/2026

describe("normalizePhone", () => {
  it.each([
    ["0912 345 678", "0912345678"],
    ["+84912345678", "0912345678"],
    ["0912.345.678", "0912345678"],
  ])("%s → %s", (input, expected) => {
    expect(normalizePhone(input)).toBe(expected);
  });

  it.each(["912345678", "09123", "abc"])("từ chối %s", (input) => {
    expect(normalizePhone(input)).toBeNull();
  });
});

describe("parseBirthDate", () => {
  it("đổi ngày/tháng/năm sang ISO", () => {
    expect(parseBirthDate("12/03/1994", TODAY)).toBe("1994-03-12");
    expect(parseBirthDate("1/2/2000", TODAY)).toBe("2000-02-01");
  });

  it.each(["31/02/2000", "17/10/2026", "01/01/1899", "1994-03-12", ""])("từ chối %s", (input) => {
    expect(parseBirthDate(input, TODAY)).toBeNull();
  });
});

it("formatBirthDateInput tự chèn dấu /", () => {
  expect(formatBirthDateInput("12031994")).toBe("12/03/1994");
  expect(formatBirthDateInput("1203")).toBe("12/03");
  expect(formatBirthDateInput("12/03/19945")).toBe("12/03/1994");
});

describe("passwordStrength", () => {
  it.each([
    ["lan2026", "weak"],
    ["matkhau123", "medium"],
    ["MatKhau-2026!", "strong"],
    ["mậtkhẩu12", "medium"],
  ])("%s → %s", (password, expected) => {
    expect(passwordStrength(password)).toBe(expected);
  });
});

describe("registerSchema", () => {
  const valid = {
    full_name: "Nguyễn Thị Lan",
    email: "lan@example.com",
    phone: "0912 345 678",
    birth_date: "12/03/1994",
    gender: "FEMALE" as const,
    password: "matkhau123",
    privacy_consent: true as const,
  };

  it("chấp nhận dữ liệu hợp lệ", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true);
  });

  it("bắt buộc đồng ý chính sách dữ liệu", () => {
    const result = registerSchema.safeParse({ ...valid, privacy_consent: false });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toBe(
      "Bạn cần đồng ý chính sách xử lý dữ liệu để đăng ký.",
    );
  });

  it("báo lỗi khi chưa chọn giới tính", () => {
    const result = registerSchema.safeParse({ ...valid, gender: undefined });
    expect(result.error?.issues[0]?.message).toBe("Vui lòng chọn giới tính.");
  });
});
