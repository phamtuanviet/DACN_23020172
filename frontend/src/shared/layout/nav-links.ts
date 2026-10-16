import type { Role } from "@/shared/auth/auth-store";
import { TEXT } from "@/shared/texts";

export type NavLink = { href: string; label: string };

export const GUEST_LINKS: NavLink[] = [
  { href: "/services", label: TEXT.nav.services },
  { href: "/services?tab=doctors", label: TEXT.nav.doctors },
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

/** Liên kết đang mở: so phần đường dẫn, bỏ query (Bác sĩ và Dịch vụ cùng là /services). */
export function isActive(pathname: string, href: string): boolean {
  const path = href.split("?")[0];
  return path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(`${path}/`);
}
