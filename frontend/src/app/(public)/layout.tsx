import type { ReactNode } from "react";

import { MobileTabBar } from "@/shared/layout/mobile-tab-bar";
import { SiteFooter } from "@/shared/layout/site-footer";
import { SiteHeader } from "@/shared/layout/site-header";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <div className="pb-16 md:pb-0">
        {children}
        <SiteFooter />
      </div>
      <MobileTabBar />
    </>
  );
}
