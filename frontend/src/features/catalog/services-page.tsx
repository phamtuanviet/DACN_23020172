// Trang Dịch vụ và bác sĩ (G-services): tìm có dấu hay không dấu (FR-CAT-04), lọc theo chuyên
// khoa, hai tab kết quả. Mọi bộ lọc nằm trên URL nên trang render phía server và chia sẻ được.
import Image from "next/image";
import Link from "next/link";

import type { Doctor, Service, Specialty } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { buttonClass } from "@/shared/ui/button";
import { ChatIcon, GridIcon, SearchIcon } from "@/shared/ui/icons";

import { getSpecialties, searchDoctors, searchServices } from "./api";
import { DoctorCard, earliestServiceOf } from "./doctor-card";
import { SearchForm } from "./search-form";
import { ServiceCard } from "./service-card";
import { specialtyMedia } from "@/shared/lib/specialty-media";

export type ServicesTab = "services" | "doctors";

type Filters = { q?: string; specialtyId?: number; tab: ServicesTab };

function servicesHref({ q, specialtyId, tab }: Partial<Filters>): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (specialtyId !== undefined) params.set("specialty", String(specialtyId));
  if (tab === "doctors") params.set("tab", "doctors");
  const query = params.toString();
  return query ? `/services?${query}` : "/services";
}

export async function ServicesPage({ q, specialtyId, tab }: Filters) {
  const [specialties, services, doctors] = await Promise.all([
    getSpecialties(),
    searchServices({ q, specialtyId }),
    searchDoctors({ q, specialtyId }),
  ]);
  const total = specialties.reduce((sum, s) => sum + s.service_count, 0);
  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-4 pt-6 pb-24 md:px-6 md:pt-8">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-[26px] leading-[34px] font-bold tracking-[-0.01em] md:text-[32px] md:leading-10">
          {TEXT.catalog.title}
        </h1>
        <p className="text-muted">{TEXT.catalog.lead(total, specialties.length)}</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <SearchForm
          key={q ?? ""}
          defaultValue={q}
          placeholder={TEXT.catalog.searchPlaceholder}
          hidden={{
            specialty: specialtyId !== undefined ? String(specialtyId) : undefined,
            tab: tab === "doctors" ? "doctors" : undefined,
          }}
          clearHref={q ? servicesHref({ specialtyId, tab }) : undefined}
        />
        {q ? <span className="text-sm text-muted">{TEXT.catalog.resultsFor(q)}</span> : null}
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <SpecialtyFilter
          specialties={specialties}
          filters={{ q, specialtyId, tab }}
          total={total}
        />
        <section className="flex min-w-0 flex-col gap-3.5">
          <ResultTabs
            filters={{ q, specialtyId, tab }}
            services={services.length}
            doctors={doctors.length}
          />
          {tab === "doctors" ? (
            <DoctorResults doctors={doctors} q={q} />
          ) : (
            <ServiceResults services={services} q={q} />
          )}
          <AssistantHint />
        </section>
      </div>
    </main>
  );
}

function SpecialtyFilter({
  specialties,
  filters,
  total,
}: {
  specialties: Specialty[];
  filters: Filters;
  total: number;
}) {
  const chipBase =
    "flex shrink-0 items-center gap-2.5 rounded-full border py-1.5 pr-3 pl-1.5 lg:rounded-[10px] lg:px-2.5 lg:py-2";
  const chipIdle =
    "border-line bg-surface lg:border-transparent lg:bg-transparent lg:hover:border-line lg:hover:bg-surface";
  const chipActive = "border-primary bg-primary-soft font-semibold text-primary-ink";
  const thumb =
    "relative size-7 shrink-0 overflow-hidden rounded-full lg:size-10 lg:rounded-[10px]";
  return (
    <nav aria-label={TEXT.catalog.filterLabel} className="min-w-0">
      <h2 className="mb-2 text-sm font-semibold tracking-[0.04em] text-muted uppercase max-lg:hidden">
        {TEXT.catalog.filterTitle}
      </h2>
      <ul className="flex gap-1.5 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
        <li>
          <Link
            href={servicesHref({ q: filters.q, tab: filters.tab })}
            aria-current={filters.specialtyId === undefined ? "true" : undefined}
            className={cn(chipBase, filters.specialtyId === undefined ? chipActive : chipIdle)}
          >
            <span
              className={cn(
                thumb,
                "flex items-center justify-center bg-primary-soft text-primary-ink",
              )}
            >
              <GridIcon size={18} />
            </span>
            <span className="flex-1 whitespace-nowrap">{TEXT.catalog.all}</span>
            <span className="text-sm text-muted max-lg:hidden">{total}</span>
          </Link>
        </li>
        {specialties.map((specialty) => {
          const media = specialtyMedia(specialty.name);
          const selected = filters.specialtyId === specialty.id;
          return (
            <li key={specialty.id}>
              <Link
                href={servicesHref({ q: filters.q, tab: filters.tab, specialtyId: specialty.id })}
                aria-current={selected ? "true" : undefined}
                className={cn(chipBase, selected ? chipActive : chipIdle)}
              >
                <span className={cn(thumb, "bg-[#dce8e7]")}>
                  <Image
                    src={media.src}
                    alt=""
                    fill
                    sizes="40px"
                    className="object-cover"
                    style={{ objectPosition: media.position }}
                  />
                </span>
                <span className="flex-1 whitespace-nowrap">{specialty.name}</span>
                <span className="text-sm text-muted max-lg:hidden">{specialty.service_count}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function ResultTabs({
  filters,
  services,
  doctors,
}: {
  filters: Filters;
  services: number;
  doctors: number;
}) {
  const tabs: { tab: ServicesTab; label: string }[] = [
    { tab: "services", label: TEXT.catalog.servicesTab(services) },
    { tab: "doctors", label: TEXT.catalog.doctorsTab(doctors) },
  ];
  return (
    <nav aria-label={TEXT.catalog.resultTabs} className="flex gap-1 border-b border-line">
      {tabs.map(({ tab, label }) => {
        const selected = filters.tab === tab;
        return (
          <Link
            key={tab}
            href={servicesHref({ ...filters, tab })}
            aria-current={selected ? "page" : undefined}
            className={cn(
              "-mb-px flex h-11 items-center border-b-2 px-4",
              selected
                ? "border-primary font-semibold text-primary-ink"
                : "border-transparent text-muted hover:text-ink",
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function ServiceResults({ services, q }: { services: Service[]; q?: string }) {
  if (services.length === 0) return <EmptyState title={TEXT.catalog.noServices(q ?? "")} />;
  const ids = services.map((s) => s.id);
  return (
    <div className="flex flex-col gap-3.5">
      {services.map((service, index) => (
        <ServiceCard key={service.id} service={service} serviceIds={ids} scopeOpen={index === 0} />
      ))}
    </div>
  );
}

function DoctorResults({ doctors, q }: { doctors: Doctor[]; q?: string }) {
  if (doctors.length === 0) return <EmptyState title={TEXT.catalog.noDoctors(q ?? "")} />;
  const ids = doctors
    .map((d) => earliestServiceOf(d))
    .filter((id): id is number => id !== undefined);
  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {doctors.map((doctor) => (
        <li key={doctor.id}>
          <DoctorCard doctor={doctor} serviceIds={ids} layout="row" className="h-full" />
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-line-strong bg-surface px-6 py-10 text-center">
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full bg-ground text-muted"
      >
        <SearchIcon size={22} />
      </span>
      <b className="text-lg">{title}</b>
      <span className="max-w-md text-muted">{TEXT.catalog.noResultsHint}</span>
      <Link href="/services" className={buttonClass({ variant: "secondary", className: "mt-2" })}>
        {TEXT.catalog.showAll}
      </Link>
    </div>
  );
}

function AssistantHint() {
  return (
    <p className="flex items-center gap-3 rounded-card border border-dashed border-[#9aaaae] px-4 py-3.5">
      <ChatIcon size={22} className="shrink-0 text-primary" />
      <span>
        <b>{TEXT.catalog.assistantTitle}</b> {TEXT.catalog.assistantBody}{" "}
        <span className="text-muted">{TEXT.home.assistantSoon}</span>
      </span>
    </p>
  );
}
