import type { Metadata } from "next";
import { Suspense } from "react";

import { AdminSchedulePage } from "@/features/admin";

export const metadata: Metadata = { title: "Ca làm và ngày nghỉ" };

/** Chưa chọn bác sĩ: trang tự mở bác sĩ đầu tiên. */
export default function Page() {
  return (
    <Suspense>
      <AdminSchedulePage />
    </Suspense>
  );
}
