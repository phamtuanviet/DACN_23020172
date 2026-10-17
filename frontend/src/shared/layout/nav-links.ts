import type { Role } from "@/shared/auth/auth-store";
import { TEXT } from "@/shared/texts";

/** `also`: các đường dẫn khác cũng tính là đang ở mục này (hồ sơ bác sĩ thuộc mục Bác sĩ). */
export type NavLink = { href: string; label: string; also?: string[] };

export const GUEST_LINKS: NavLink[] = [
  { href: "/services", label: TEXT.nav.services },
  { href: "/services?tab=doctors", label: TEXT.nav.doctors, also: ["/doctors"] },
  { href: "/booking", label: TEXT.nav.booking },
];

export const PATIENT_LINKS: NavLink[] = [
  { href: "/booking", label: TEXT.nav.booking },
  { href: "/me/appointments", label: TEXT.nav.myAppointments },
  { href: "/services", label: TEXT.nav.services },
];

export const STAFF_LINKS: Record<Exclude<Role, "PATIENT">, NavLink[]> = {
  DOCTOR: [{ href: "/doctor/schedule", label: TEXT.staff.schedule }],
  ADMIN: [
    { href: "/admin/dashboard", label: TEXT.staff.dashboard },
    { href: "/admin/appointments", label: TEXT.staff.appointments },
    { href: "/admin/catalog", label: TEXT.staff.catalog },
    { href: "/admin/doctors", label: TEXT.staff.doctors },
  ],
};

/** Liên kết đang mở: so phần đường dẫn, bỏ query. */
export function isActive(pathname: string, href: string): boolean {
  const path = href.split("?")[0];
  return path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(`${path}/`);
}

/** Như `isActive` nhưng phân biệt hai mục cùng đường dẫn bằng `tab` (Dịch vụ và Bác sĩ cùng là
 *  /services, khác ở ?tab=doctors). */
export function isNavLinkActive(link: NavLink, pathname: string, search: string): boolean {
  if (link.also?.some((path) => isActive(pathname, path))) return true;
  if (!isActive(pathname, link.href)) return false;
  const wanted = new URLSearchParams(link.href.split("?")[1] ?? "").get("tab");
  return wanted === new URLSearchParams(search).get("tab");
}
