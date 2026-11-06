import type { Metadata } from "next";
import { Suspense } from "react";

import { DoctorSchedulePage } from "@/features/doctor";

export const metadata: Metadata = { title: "Lịch khám" };

export default function Page() {
  return (
    <Suspense>
      <DoctorSchedulePage />
    </Suspense>
  );
}
