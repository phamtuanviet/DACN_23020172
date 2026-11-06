import type { Metadata } from "next";
import { Suspense } from "react";

import { AdminSchedulePage } from "@/features/admin";

export const metadata: Metadata = { title: "Ca làm và ngày nghỉ" };

export default async function Page({ params }: { params: Promise<{ doctorId: string }> }) {
  const id = Number((await params).doctorId);
  return (
    <Suspense>
      <AdminSchedulePage doctorId={Number.isInteger(id) && id > 0 ? id : undefined} />
    </Suspense>
  );
}
