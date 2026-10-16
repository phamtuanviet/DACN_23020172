import { Suspense, type ReactNode } from "react";

import { RoleGuard } from "@/shared/auth/role-guard";
import { StaffShell } from "@/shared/layout/staff-shell";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <Suspense>
      <RoleGuard roles={["DOCTOR"]}>
        <StaffShell role="DOCTOR">{children}</StaffShell>
      </RoleGuard>
    </Suspense>
  );
}
