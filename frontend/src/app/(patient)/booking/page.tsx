import type { Metadata } from "next";
import { Suspense } from "react";

import { BookingWizard } from "@/features/booking";

export const metadata: Metadata = { title: "Đặt lịch" };

export default function Page() {
  return (
    <Suspense>
      <BookingWizard />
    </Suspense>
  );
}
