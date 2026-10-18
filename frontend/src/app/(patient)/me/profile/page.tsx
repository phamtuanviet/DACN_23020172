import type { Metadata } from "next";

import { ProfileScreen } from "@/features/auth";

export const metadata: Metadata = { title: "Hồ sơ cá nhân" };

export default function Page() {
  return <ProfileScreen />;
}
