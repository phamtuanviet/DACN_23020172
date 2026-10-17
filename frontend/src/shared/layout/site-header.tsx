"use client";

// Đầu trang của khách và bệnh nhân (G-home, P-book): menu đầy đủ từ 1024px; 768–1024px gom vào
// nút menu; dưới 768px điều hướng chuyển xuống thanh tab đáy màn hình (MobileTabBar).
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";

import { useAuthStore } from "@/shared/auth/auth-store";
import { ROLE_HOME } from "@/shared/auth/navigation";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { buttonClass } from "@/shared/ui/button";
import { CloseIcon, MenuIcon } from "@/shared/ui/icons";
import { Logo } from "@/shared/ui/logo";

import { AccountMenu } from "./account-menu";
import { GUEST_LINKS, isNavLinkActive, PATIENT_LINKS } from "./nav-links";

export function SiteHeader() {
  const status = useAuthStore((state) => state.status);
  const user = useAuthStore((state) => state.user);
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const [menuOpen, setMenuOpen] = useState(false);
  const links = user?.role === "PATIENT" ? PATIENT_LINKS : GUEST_LINKS;

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-3 px-4 md:gap-7 md:px-6">
        <Logo className="min-w-0" />
        <nav aria-label={TEXT.nav.mainNav} className="hidden flex-1 gap-1 lg:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={isNavLinkActive(link, pathname, search) ? "page" : undefined}
              className={cn(
                "rounded-control px-3.5 py-2.5 whitespace-nowrap",
                isNavLinkActive(link, pathname, search)
                  ? "bg-primary-soft font-semibold text-primary-ink"
                  : "hover:bg-ground",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {status === "authenticated" && user ? (
            <>
              {user.role !== "PATIENT" ? (
                <Link
                  href={ROLE_HOME[user.role]}
                  className={buttonClass({ variant: "secondary", className: "max-md:hidden" })}
                >
                  {TEXT.nav.account}
                </Link>
              ) : null}
              <AccountMenu user={user} />
            </>
          ) : null}
          {status === "anonymous" ? (
            <>
              <Link
                href="/login"
                className={buttonClass({ variant: "ghost", className: "max-md:h-10 max-md:px-3" })}
              >
                {TEXT.nav.login}
              </Link>
              <Link href="/booking" className={buttonClass({ className: "max-md:hidden" })}>
                {TEXT.nav.bookNow}
              </Link>
            </>
          ) : null}
          <button
            type="button"
            aria-label={menuOpen ? TEXT.nav.closeMenu : TEXT.nav.openMenu}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((value) => !value)}
            className="hidden size-11 items-center justify-center rounded-control border border-line-strong md:flex lg:hidden"
          >
            {menuOpen ? <CloseIcon size={22} /> : <MenuIcon size={22} />}
          </button>
        </div>
      </div>

      {menuOpen ? (
        <nav
          aria-label={TEXT.nav.mainNav}
          className="hidden border-t border-line bg-surface px-6 py-3 md:block lg:hidden"
        >
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={isNavLinkActive(link, pathname, search) ? "page" : undefined}
              onClick={() => setMenuOpen(false)}
              className="block rounded-control px-3 py-3 font-medium hover:bg-ground"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      ) : null}
    </header>
  );
}
