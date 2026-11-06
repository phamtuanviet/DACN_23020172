import type { Metadata } from "next";

import { AdminDoctorsPage } from "@/features/admin";

export const metadata: Metadata = { title: "Bác sĩ" };

export default function Page() {
  return <AdminDoctorsPage />;
}
