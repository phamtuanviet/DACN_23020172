import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DoctorAppointmentPage } from "@/features/doctor";

export const metadata: Metadata = { title: "Chi tiết lịch hẹn" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id <= 0) notFound();
  return <DoctorAppointmentPage id={id} />;
}
