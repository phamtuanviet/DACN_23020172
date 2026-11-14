import type { Metadata } from "next";
import { Suspense } from "react";

import { AdminDashboardPage } from "@/features/admin";

export const metadata: Metadata = { title: "Tổng quan" };

export default function Page() {
  return (
    <Suspense>
      <AdminDashboardPage />
    </Suspense>
  );
}
