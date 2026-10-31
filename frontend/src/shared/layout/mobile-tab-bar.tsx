"use client";

// Thanh tab dưới đáy màn hình điện thoại (dưới 768px), giống G-home-m và P-appts-m.
// Tab Trợ lý mở khung chat toàn màn hình; khách bấm thì đăng nhập rồi quay lại với khung chat mở.
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";

import { loginHrefForChat, useChatPanel } from "@/shared/agent/chat-panel-store";
import { useAuthStore } from "@/shared/auth/auth-store";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { CalendarPlusIcon, ChatIcon, HomeIcon, ListIcon, UserIcon } from "@/shared/ui/icons";

import { isActive } from "./nav-links";

type Tab = {
  href: string;
  label: string;
  Icon: ComponentType<{ size?: number; strokeWidth?: number }>;
};

const TAB_CLASS = "flex flex-col items-center justify-center gap-0.5 text-[11px] leading-[14px]";

export function MobileTabBar() {
  const pathname = usePathname();
  const loggedIn = useAuthStore((state) => state.status === "authenticated");
  const role = useAuthStore((state) => state.user?.role);
  const chatOpen = useChatPanel((state) => state.open);
  const toggleChat = useChatPanel((state) => state.toggleChat);
  const withAssistant = !loggedIn || role === "PATIENT";
  const tabs: Tab[] = [
    { href: "/", label: TEXT.nav.home, Icon: HomeIcon },
    { href: "/booking", label: TEXT.nav.booking, Icon: CalendarPlusIcon },
    { href: "/me/appointments", label: TEXT.nav.myAppointments, Icon: ListIcon },
  ];
  const account: Tab = loggedIn
    ? { href: "/me/profile", label: TEXT.nav.account, Icon: UserIcon }
    : { href: "/login", label: TEXT.nav.login, Icon: UserIcon };

  const link = ({ href, label, Icon }: Tab) => {
    const active = !chatOpen && isActive(pathname, href);
    return (
      <Link
        key={href}
        href={href}
        aria-current={active ? "page" : undefined}
        className={cn(TAB_CLASS, active ? "font-semibold text-primary" : "text-muted")}
      >
        <Icon size={22} strokeWidth={active ? 2.2 : 2} />
        {label}
      </Link>
    );
  };

  return (
    <nav
      aria-label={TEXT.nav.mobileNav}
      className={cn(
        "fixed inset-x-0 bottom-0 z-30 grid h-16 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden",
        withAssistant ? "grid-cols-5" : "grid-cols-4",
      )}
    >
      {tabs.map(link)}
      {role === "PATIENT" ? (
        <button
          type="button"
          onClick={toggleChat}
          aria-expanded={chatOpen}
          className={cn(TAB_CLASS, chatOpen ? "font-semibold text-primary" : "text-muted")}
        >
          <ChatIcon size={22} strokeWidth={chatOpen ? 2.2 : 2} />
          {TEXT.nav.assistant}
        </button>
      ) : withAssistant ? (
        <Link href={loginHrefForChat(pathname)} className={cn(TAB_CLASS, "text-muted")}>
          <ChatIcon size={22} />
          {TEXT.nav.assistant}
        </Link>
      ) : null}
      {link(account)}
    </nav>
  );
}
