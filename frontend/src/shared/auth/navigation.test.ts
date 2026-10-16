import { describe, expect, it } from "vitest";

import { landingPath, loginHref, safeNext } from "./navigation";

describe("safeNext", () => {
  it("nhận đường dẫn nội bộ", () => {
    expect(safeNext("/booking?service=3")).toBe("/booking?service=3");
  });

  it.each(["https://evil.example", "//evil.example", "/\\evil.example", "booking", "", null])(
    "chặn chuyển hướng ra ngoài hoặc không hợp lệ: %s",
    (value) => {
      expect(safeNext(value)).toBeNull();
    },
  );

  it.each(["/\t/evil.example", "/\n/evil.example", "/\r/evil.example", "/\u007f/evil.example"])(
    "chặn ký tự điều khiển mà trình duyệt sẽ bỏ đi thành //evil: %j",
    (value) => {
      expect(safeNext(value)).toBeNull();
    },
  );

  it("giữ nguyên ký tự đã mã hóa vì đường dẫn vẫn ở trong trang", () => {
    expect(safeNext("/%09/evil.example")).toBe("/%09/evil.example");
  });

  it("không quay lại chính trang đăng nhập, đăng ký", () => {
    expect(safeNext("/login?next=/booking")).toBeNull();
  });
});

describe("landingPath", () => {
  it("về trang đang dở nếu thuộc vai trò vừa đăng nhập", () => {
    expect(landingPath("PATIENT", "/booking?service=3")).toBe("/booking?service=3");
  });

  it("về khu vực của vai trò khi next thuộc vai trò khác", () => {
    expect(landingPath("DOCTOR", "/booking")).toBe("/doctor/schedule");
    expect(landingPath("PATIENT", "/admin/appointments")).toBe("/me/appointments");
  });

  it("mặc định theo vai trò", () => {
    expect(landingPath("ADMIN", null)).toBe("/admin/appointments");
  });
});

it("loginHref mã hóa next", () => {
  expect(loginHref("/booking?service=3&doctor=7")).toBe(
    "/login?next=%2Fbooking%3Fservice%3D3%26doctor%3D7",
  );
});
