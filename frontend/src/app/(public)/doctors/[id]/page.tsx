import type { Metadata } from "next";

import { DoctorPage, loadDoctor } from "@/features/catalog";

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Pick<Props, "params">): Promise<Metadata> {
  const doctor = await loadDoctor(Number((await params).id));
  return { title: doctor.name, description: doctor.bio ?? undefined };
}

export default async function Page({ params, searchParams }: Props) {
  const { id } = await params;
  const service = Number((await searchParams).service);
  return <DoctorPage id={Number(id)} serviceId={Number.isInteger(service) ? service : undefined} />;
}
