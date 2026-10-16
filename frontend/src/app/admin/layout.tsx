import { Suspense, type ReactNode } from "react";

import { RoleGuard } from "@/shared/auth/role-guard";
import { StaffShell } from "@/shared/layout/staff-shell";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <Suspense>
      <RoleGuard roles={["ADMIN"]}>
        <StaffShell role="ADMIN">{children}</StaffShell>
      </RoleGuard>
    </Suspense>
  );
}
