import { describe, expect, it } from "vitest";

import {
  GUEST_LINKS,
  isNavLinkActive,
  PATIENT_LINKS,
  STAFF_LINKS,
  type NavLink,
} from "./nav-links";

const [services, doctors, booking] = GUEST_LINKS;
const active = (link: NavLink, path: string, search = "", links = GUEST_LINKS) =>
  isNavLinkActive(link, path, search, links);

describe("isNavLinkActive", () => {
  it("phân biệt Dịch vụ và Bác sĩ cùng đường dẫn /services", () => {
    expect(active(services!, "/services", "q=da+lieu")).toBe(true);
    expect(active(doctors!, "/services", "q=da+lieu")).toBe(false);
    expect(active(services!, "/services", "tab=doctors")).toBe(false);
    expect(active(doctors!, "/services", "tab=doctors&specialty=2")).toBe(true);
  });

  it("hồ sơ bác sĩ thuộc mục Bác sĩ", () => {
    expect(active(doctors!, "/doctors/6", "service=5")).toBe(true);
    expect(active(services!, "/doctors/6", "")).toBe(false);
  });

  it("bước đặt lịch giữ mục Đặt lịch dù có query", () => {
    expect(active(booking!, "/booking", "service=5&doctor=any")).toBe(true);
  });

  it("tab của trang khác không làm mất trạng thái đang mở", () => {
    const mine = PATIENT_LINKS.find((link) => link.href === "/me/appointments")!;
    expect(active(mine, "/me/appointments", "tab=history&id=3", PATIENT_LINKS)).toBe(true);
  });

  it("Lịch hẹn và Hàng chờ của quản trị cùng đường dẫn, khác ở ?tab=queue", () => {
    const links = STAFF_LINKS.ADMIN;
    const all = links.find((link) => link.href === "/admin/appointments")!;
    const queue = links.find((link) => link.href === "/admin/appointments?tab=queue")!;
    expect(active(all, "/admin/appointments", "status=BOOKED", links)).toBe(true);
    expect(active(queue, "/admin/appointments", "status=BOOKED", links)).toBe(false);
    expect(active(all, "/admin/appointments", "tab=queue", links)).toBe(false);
    expect(active(queue, "/admin/appointments", "tab=queue", links)).toBe(true);
  });
});
