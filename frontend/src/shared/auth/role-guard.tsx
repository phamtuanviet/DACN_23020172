"use client";

import type { ReactNode } from "react";

import type { Role } from "./auth-store";

// Chỉ để điều hướng giao diện; quyền thật luôn do backend kiểm tra (docs mục 9.3).
// Cần làm: chưa có token → gọi /auth/refresh; thất bại → /login?next=…; sai vai trò → trang 403.
export function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  void roles;
  return <>{children}</>;
}
