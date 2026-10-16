"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import type { SessionUser } from "@/shared/auth/auth-store";
import { ROLE_HOME } from "@/shared/auth/navigation";
import { logout } from "@/shared/auth/session";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { ChevronDownIcon, LogoutIcon, UserIcon } from "@/shared/ui/icons";

export function initials(fullName: string): string {
  const words = fullName
    .replace(/^(ThS\.|TS\.|BS\.CKI+|BS\.)\s*/u, "")
    .trim()
    .split(/\s+/);
  return (words.at(-1)?.[0] ?? "?").toUpperCase();
}

export function shortName(fullName: string): string {
  return fullName.trim().split(/\s+/).at(-1) ?? fullName;
}

// Ô tài khoản ở đầu trang: tên ngắn + menu (hồ sơ hoặc khu vực làm việc, đăng xuất).
export function AccountMenu({
  user,
  tone = "light",
}: {
  user: SessionUser;
  tone?: "light" | "dark";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const router = useRouter();

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (
        event instanceof KeyboardEvent
          ? event.key === "Escape"
          : !ref.current?.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  async function onLogout() {
    setOpen(false);
    await logout();
    router.push("/");
  }

  const homeHref = user.role === "PATIENT" ? "/me/profile" : ROLE_HOME[user.role];
  const homeLabel = user.role === "PATIENT" ? TEXT.nav.profile : TEXT.nav.account;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "flex h-11 items-center gap-2 rounded-full border py-1 pr-3 pl-1 font-medium",
          tone === "light" ? "border-line bg-surface text-ink" : "border-white/20 text-white",
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "flex size-[34px] items-center justify-center rounded-full text-sm font-semibold",
            tone === "light" ? "bg-ink text-white" : "bg-white text-ink",
          )}
        >
          {initials(user.full_name)}
        </span>
        <span className="max-w-32 truncate">{shortName(user.full_name)}</span>
        <ChevronDownIcon size={16} />
      </button>
      {open ? (
        <div
          id={menuId}
          className="absolute right-0 z-40 mt-2 w-60 overflow-hidden rounded-card border border-line bg-surface py-1 text-ink shadow-lg"
        >
          <div className="border-b border-divider px-4 py-3">
            <p className="truncate font-semibold">{user.full_name}</p>
            <p className="truncate text-sm text-muted">{user.email}</p>
          </div>
          <Link
            href={homeHref}
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-ground"
          >
            <UserIcon size={18} />
            {homeLabel}
          </Link>
          <button
            type="button"
            onClick={onLogout}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-danger hover:bg-danger-soft"
          >
            <LogoutIcon size={18} />
            {TEXT.nav.logout}
          </button>
        </div>
      ) : null}
    </div>
  );
}
