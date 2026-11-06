import type { Metadata } from "next";

import { StaffAccountScreen } from "@/features/auth";

export const metadata: Metadata = { title: "Tài khoản" };

export default function Page() {
  return <StaffAccountScreen />;
}
