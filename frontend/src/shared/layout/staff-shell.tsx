"use client";

// Khung làm việc của bác sĩ và quản trị (D-day, AD-*): thanh bên màu tối từ 1024px; nhỏ hơn thì
// thanh trên màu tối với nút mở menu dạng ngăn kéo. Mục Hàng chờ của quản trị kèm số việc đang chờ.
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type ComponentType, type ReactNode } from "react";

import { useQueueCount } from "@/shared/admin/queue";
import { useAuthStore } from "@/shared/auth/auth-store";
import { logout } from "@/shared/auth/session";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import {
  CalendarIcon,
  CalendarPlusIcon,
  ChartIcon,
  CloseIcon,
  FlagIcon,
  GridIcon,
  ListIcon,
  LogoutIcon,
  MenuIcon,
  UsersIcon,
} from "@/shared/ui/icons";
import { Logo } from "@/shared/ui/logo";

import { initials } from "./account-menu";
import { isNavLinkActive, STAFF_LINKS } from "./nav-links";

const QUEUE_HREF = "/admin/appointments?tab=queue";
const ICONS: Record<string, ComponentType<{ size?: number }>> = {
  "/doctor/schedule": CalendarPlusIcon,
  "/admin/dashboard": ChartIcon,
  "/admin/appointments": ListIcon,
  [QUEUE_HREF]: FlagIcon,
  "/admin/catalog": GridIcon,
  "/admin/doctors": UsersIcon,
  "/admin/schedules": CalendarIcon,
};

export function StaffShell({ role, children }: { role: "DOCTOR" | "ADMIN"; children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const area = role === "ADMIN" ? TEXT.staff.adminArea : TEXT.staff.doctorArea;
  const links = STAFF_LINKS[role];
  const isCurrent = (href: string) => {
    const link = links.find((item) => item.href === href);
    return link ? isNavLinkActive(link, pathname, search, links) : false;
  };
  const current = links.find((link) => isCurrent(link.href));
  const homeHref = links[0]?.href ?? "/";
  const queueCount = useQueueCount(role === "ADMIN").data ?? 0;

  async function onLogout() {
    await logout();
    router.push("/login");
  }

  const nav = (
    <nav aria-label={area} className="flex flex-1 flex-col gap-1">
      {links.map((link) => {
        const Icon = ICONS[link.href] ?? ListIcon;
        const active = isCurrent(link.href);
        const badge = link.href === QUEUE_HREF && queueCount > 0 ? queueCount : null;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            onClick={() => setDrawerOpen(false)}
            className={cn(
              "flex items-center gap-3 rounded-control px-3 py-2.5",
              active
                ? "bg-white/12 font-semibold text-white"
                : "text-[#c9d5d8] hover:bg-white/6 hover:text-white",
            )}
          >
            <Icon size={20} />
            <span className="flex-1">{link.label}</span>
            {badge !== null ? (
              <span
                aria-label={TEXT.staff.queueCount(badge)}
                className="rounded-full bg-[#ffe3a8] px-2 text-[13px] leading-5 font-bold text-amber-ink"
              >
                {badge}
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );

  const userBlock = user ? (
    <div className="flex items-center gap-3 border-t border-white/10 pt-4">
      <span
        aria-hidden="true"
        className="flex size-9 items-center justify-center rounded-full bg-white text-sm font-semibold text-ink"
      >
        {initials(user.full_name)}
      </span>
      <Link
        href={role === "ADMIN" ? "/admin/account" : "/doctor/account"}
        title={TEXT.profile.openAccount}
        onClick={() => setDrawerOpen(false)}
        className="min-w-0 flex-1 rounded-control hover:bg-white/6"
      >
        <span className="block truncate text-sm font-semibold text-white">{user.full_name}</span>
        <span className="block text-xs text-[#9fb0b4]">{area}</span>
      </Link>
      <button
        type="button"
        onClick={onLogout}
        aria-label={TEXT.nav.logout}
        title={TEXT.nav.logout}
        className="rounded-control p-2 text-[#c9d5d8] hover:bg-white/10 hover:text-white"
      >
        <LogoutIcon size={20} />
      </button>
    </div>
  ) : null;

  return (
    <div className="min-h-screen bg-ground">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col gap-6 bg-ink px-4 py-5 lg:flex">
        <Logo inverted href={homeHref} />
        {nav}
        {userBlock}
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center gap-1 bg-ink px-2 text-white lg:hidden">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label={TEXT.nav.openMenu}
          aria-expanded={drawerOpen}
          className="flex size-11 items-center justify-center rounded-control hover:bg-white/10"
        >
          <MenuIcon size={22} />
        </button>
        <span className="flex-1 truncate text-[17px] font-semibold">{current?.label ?? area}</span>
      </header>

      {drawerOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label={TEXT.nav.closeMenu}
            className="absolute inset-0 bg-ink/50"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="relative flex h-full w-72 max-w-[85%] flex-col gap-6 bg-ink px-4 py-5">
            <div className="flex items-center justify-between">
              <Logo inverted href={homeHref} />
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                aria-label={TEXT.nav.closeMenu}
                className="rounded-control p-2 text-white hover:bg-white/10"
              >
                <CloseIcon size={22} />
              </button>
            </div>
            {nav}
            {userBlock}
          </div>
        </div>
      ) : null}

      <div className="lg:pl-64">{children}</div>
    </div>
  );
}
