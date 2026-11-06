import type { Metadata } from "next";
import { Suspense } from "react";

import { AdminCatalogPage } from "@/features/admin";

export const metadata: Metadata = { title: "Danh mục" };

export default function Page() {
  return (
    <Suspense>
      <AdminCatalogPage />
    </Suspense>
  );
}
