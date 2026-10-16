"use client";

// Thanh tab dưới đáy màn hình điện thoại (dưới 768px), giống G-home-m và P-appts-m.
// Mục Trợ lý được thêm ở Sprint 4 khi có khung chat.
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";

import { useAuthStore } from "@/shared/auth/auth-store";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { CalendarPlusIcon, HomeIcon, ListIcon, UserIcon } from "@/shared/ui/icons";

import { isActive } from "./nav-links";

type Tab = {
  href: string;
  label: string;
  Icon: ComponentType<{ size?: number; strokeWidth?: number }>;
};

export function MobileTabBar() {
  const pathname = usePathname();
  const loggedIn = useAuthStore((state) => state.status === "authenticated");
  const tabs: Tab[] = [
    { href: "/", label: TEXT.nav.home, Icon: HomeIcon },
    { href: "/booking", label: TEXT.nav.booking, Icon: CalendarPlusIcon },
    { href: "/me/appointments", label: TEXT.nav.myAppointments, Icon: ListIcon },
    loggedIn
      ? { href: "/me/profile", label: TEXT.nav.account, Icon: UserIcon }
      : { href: "/login", label: TEXT.nav.login, Icon: UserIcon },
  ];

  return (
    <nav
      aria-label={TEXT.nav.mobileNav}
      className="fixed inset-x-0 bottom-0 z-30 grid h-16 grid-cols-4 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {tabs.map(({ href, label, Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-col items-center justify-center gap-0.5 text-[11px] leading-[14px]",
              active ? "font-semibold text-primary" : "text-muted",
            )}
          >
            <Icon size={22} strokeWidth={active ? 2.2 : 2} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
