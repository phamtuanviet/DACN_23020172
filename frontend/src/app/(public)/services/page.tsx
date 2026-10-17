import type { Metadata } from "next";

import { ServicesPage, type ServicesTab } from "@/features/catalog";

export const metadata: Metadata = { title: "Dịch vụ và bác sĩ" };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function Page({ searchParams }: Props) {
  const params = await searchParams;
  const q = first(params.q)?.trim().slice(0, 100) || undefined;
  const specialty = Number(first(params.specialty));
  const tab: ServicesTab = first(params.tab) === "doctors" ? "doctors" : "services";
  return (
    <ServicesPage
      q={q}
      specialtyId={Number.isInteger(specialty) && specialty > 0 ? specialty : undefined}
      tab={tab}
    />
  );
}
