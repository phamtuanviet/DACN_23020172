import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginScreen } from "@/features/auth";

export const metadata: Metadata = { title: "Đăng nhập" };

export default function Page() {
  return (
    <Suspense>
      <LoginScreen />
    </Suspense>
  );
}
