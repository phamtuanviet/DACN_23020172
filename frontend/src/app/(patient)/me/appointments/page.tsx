import type { Metadata } from "next";
import { Suspense } from "react";

import { MyAppointmentsPage } from "@/features/my-appointments";

export const metadata: Metadata = { title: "Lịch của tôi" };

export default function Page() {
  return (
    <Suspense>
      <MyAppointmentsPage />
    </Suspense>
  );
}
