import { describe, expect, it } from "vitest";

import { GUEST_LINKS, isNavLinkActive } from "./nav-links";

const [services, doctors, booking] = GUEST_LINKS;

describe("isNavLinkActive", () => {
  it("phân biệt Dịch vụ và Bác sĩ cùng đường dẫn /services", () => {
    expect(isNavLinkActive(services!, "/services", "q=da+lieu")).toBe(true);
    expect(isNavLinkActive(doctors!, "/services", "q=da+lieu")).toBe(false);
    expect(isNavLinkActive(services!, "/services", "tab=doctors")).toBe(false);
    expect(isNavLinkActive(doctors!, "/services", "tab=doctors&specialty=2")).toBe(true);
  });

  it("hồ sơ bác sĩ thuộc mục Bác sĩ", () => {
    expect(isNavLinkActive(doctors!, "/doctors/6", "service=5")).toBe(true);
    expect(isNavLinkActive(services!, "/doctors/6", "")).toBe(false);
  });

  it("bước đặt lịch giữ mục Đặt lịch dù có query", () => {
    expect(isNavLinkActive(booking!, "/booking", "service=5&doctor=any")).toBe(true);
  });
});
