// Điều hướng sau đăng nhập: về ?next= nếu hợp lệ, không thì về khu vực của vai trò (G-login).
import type { Role } from "./auth-store";

export const ROLE_HOME: Record<Role, string> = {
  PATIENT: "/me/appointments",
  DOCTOR: "/doctor/schedule",
  ADMIN: "/admin/appointments",
};

// Trình duyệt bỏ tab, xuống dòng khi phân tích URL ("/\t/evil" thành "//evil") và coi "\" như "/",
// nên các ký tự này bị từ chối trước khi so origin.
function hasControlOrBackslash(value: string): boolean {
  return [...value].some(
    (ch) => ch.charCodeAt(0) < 0x20 || ch.charCodeAt(0) === 0x7f || ch === "\\",
  );
}

/** Chỉ nhận đường dẫn nội bộ ("/booking?service=3"), chặn chuyển hướng ra trang ngoài. */
export function safeNext(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || hasControlOrBackslash(next))
    return null;
  const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  let url: URL;
  try {
    url = new URL(next, origin);
  } catch {
    return null;
  }
  if (url.origin !== origin) return null;
  const path = `${url.pathname}${url.search}${url.hash}`;
  if (path.startsWith("/login") || path.startsWith("/register")) return null;
  return path;
}

/** `next` chỉ dùng khi trang đó thuộc vai trò vừa đăng nhập; bác sĩ không bị đưa vào /booking. */
export function landingPath(role: Role, next: string | null | undefined): string {
  const target = safeNext(next);
  if (target && canVisit(role, target)) return target;
  return ROLE_HOME[role];
}

export function canVisit(role: Role, path: string): boolean {
  if (path.startsWith("/admin")) return role === "ADMIN";
  if (path.startsWith("/doctor")) return role === "DOCTOR";
  if (path.startsWith("/booking") || path.startsWith("/me")) return role === "PATIENT";
  return true;
}

export function loginHref(next: string): string {
  return `/login?next=${encodeURIComponent(next)}`;
}
