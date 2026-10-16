"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { buttonClass } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Spinner } from "@/shared/ui/spinner";
import { TEXT } from "@/shared/texts";

import { useAuthStore, type Role } from "./auth-store";
import { loginHref, ROLE_HOME } from "./navigation";

// Chỉ để điều hướng giao diện; quyền thật luôn do backend kiểm tra (docs mục 9.3).
// Chưa biết phiên → khung chờ; chưa đăng nhập → /login?next=…; sai vai trò → trang 403.
export function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const status = useAuthStore((state) => state.status);
  const role = useAuthStore((state) => state.user?.role);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (status !== "anonymous") return;
    const query = searchParams.toString();
    router.replace(loginHref(query ? `${pathname}?${query}` : pathname));
  }, [status, pathname, searchParams, router]);

  if (status !== "authenticated" || !role) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-muted">
        <Spinner label={TEXT.common.loading} />
      </div>
    );
  }

  if (!roles.includes(role)) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16">
        <Card className="flex flex-col items-center gap-3 p-8 text-center">
          <h1 className="text-xl font-semibold">{TEXT.common.forbiddenTitle}</h1>
          <p className="text-muted">{TEXT.common.forbiddenBody}</p>
          <Link href={ROLE_HOME[role]} className={buttonClass({ className: "mt-2" })}>
            {TEXT.common.goToMyArea}
          </Link>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
