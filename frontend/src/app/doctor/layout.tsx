import type { ReactNode } from "react";

import { RoleGuard } from "@/shared/auth/role-guard";

export default function Layout({ children }: { children: ReactNode }) {
  return <RoleGuard roles={["DOCTOR"]}>{children}</RoleGuard>;
}
