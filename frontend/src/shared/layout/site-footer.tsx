import Link from "next/link";

import { CLINIC, TEXT } from "@/shared/texts";
import { LogoMark } from "@/shared/ui/logo";

export function SiteFooter() {
  return (
    <footer className="bg-ink text-[15px] text-[#d5dee0]">
      <div className="mx-auto grid max-w-[1200px] gap-6 px-4 pt-10 pb-7 sm:grid-cols-2 md:px-6 lg:grid-cols-[2fr_1fr_1fr]">
        <div className="flex flex-col gap-2">
          <span className="flex items-center gap-2.5 font-bold text-white">
            <LogoMark inverted />
            {CLINIC.name}
          </span>
          {CLINIC.phone ? <span>{CLINIC.phone}</span> : null}
          <span className="font-semibold text-white">{TEXT.common.emergency}</span>
        </div>
        <nav aria-label="Khám bệnh" className="flex flex-col gap-2">
          <b className="text-white">Khám bệnh</b>
          <Link href="/services" className="hover:text-white">
            {TEXT.nav.services}
          </Link>
          <Link href="/booking" className="hover:text-white">
            {TEXT.nav.bookNow}
          </Link>
        </nav>
        <nav aria-label={TEXT.nav.account} className="flex flex-col gap-2">
          <b className="text-white">{TEXT.nav.account}</b>
          <Link href="/login" className="hover:text-white">
            {TEXT.nav.login}
          </Link>
          <Link href="/register" className="hover:text-white">
            {TEXT.nav.register}
          </Link>
          <Link href="/me/appointments" className="hover:text-white">
            {TEXT.nav.myAppointments}
          </Link>
        </nav>
      </div>
      <div className="mx-auto max-w-[1200px] border-t border-white/10 px-4 pt-4 pb-5 text-[13px] text-[#9fb0b4] md:px-6">
        © 2026 {CLINIC.name} · {TEXT.common.footerNote}
      </div>
    </footer>
  );
}
