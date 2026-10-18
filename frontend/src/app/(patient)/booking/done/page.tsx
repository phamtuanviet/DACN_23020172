import type { Metadata } from "next";
import { Suspense } from "react";

import { BookingDone } from "@/features/booking";

export const metadata: Metadata = { title: "Đặt lịch thành công" };

export default function Page() {
  return (
    <Suspense>
      <BookingDone />
    </Suspense>
  );
}
