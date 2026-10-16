import type { Metadata } from "next";
import { Suspense } from "react";

import { RegisterScreen } from "@/features/auth";

export const metadata: Metadata = { title: "Đăng ký" };

export default function Page() {
  return (
    <Suspense>
      <RegisterScreen />
    </Suspense>
  );
}
