import type { Metadata } from "next";
import { Suspense } from "react";

import { AdminAppointmentsPage } from "@/features/admin";

export const metadata: Metadata = { title: "Lịch hẹn" };

export default function Page() {
  return (
    <Suspense>
      <AdminAppointmentsPage />
    </Suspense>
  );
}
