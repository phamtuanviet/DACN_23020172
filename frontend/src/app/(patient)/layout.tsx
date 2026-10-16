import { Suspense, type ReactNode } from "react";

import { RoleGuard } from "@/shared/auth/role-guard";
import { MobileTabBar } from "@/shared/layout/mobile-tab-bar";
import { SiteHeader } from "@/shared/layout/site-header";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <div className="pb-16 md:pb-0">
        <Suspense>
          <RoleGuard roles={["PATIENT"]}>{children}</RoleGuard>
        </Suspense>
      </div>
      <MobileTabBar />
    </>
  );
}
