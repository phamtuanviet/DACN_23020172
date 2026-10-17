"use client";

// Bước 1 (P-book-1): chọn chuyên khoa rồi chọn dịch vụ, hoặc tìm thẳng theo tên, có dấu hay
// không dấu. Chuyên khoa và từ khóa nằm trên URL (thay thế, không thêm lịch sử); chọn dịch vụ thì
// sang bước 2 (thêm lịch sử) để nút Quay lại của trình duyệt về đúng bước này.
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { Service } from "@/shared/api/types";
import { bookingHref, type BookingState } from "@/shared/availability/booking-href";
import { cn } from "@/shared/lib/cn";
import { formatDuration, formatPrice } from "@/shared/lib/format";
import { specialtyMedia } from "@/shared/lib/specialty-media";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { ChatIcon, CheckIcon, SearchIcon } from "@/shared/ui/icons";

import { useServices, useSpecialties } from "./queries";

const SEARCH_DELAY_MS = 300;

export function ServiceStep({ state }: { state: BookingState }) {
  const router = useRouter();
  const specialties = useSpecialties();
  const [query, setQuery] = useState(state.q ?? "");
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const searching = Boolean(state.q);
  const specialtyId = state.specialty ?? specialties.data?.[0]?.id;
  const specialty = specialties.data?.find((s) => s.id === specialtyId);
  const services = useServices(
    searching ? { q: state.q } : { specialtyId },
    searching || specialtyId !== undefined,
  );

  function onSearch(value: string) {
    setQuery(value);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const q = value.trim() || undefined;
      router.replace(bookingHref({ specialty: state.specialty, q }), { scroll: false });
    }, SEARCH_DELAY_MS);
  }

  function pickSpecialty(id: number) {
    window.clearTimeout(timer.current);
    setQuery("");
    router.replace(bookingHref({ specialty: id }), { scroll: false });
  }

  function pickService(service: Service) {
    window.clearTimeout(timer.current);
    router.push(bookingHref({ specialty: service.specialty.id, service: service.id }));
  }

  return (
    <section className="flex flex-col gap-[22px] rounded-card border border-line bg-surface p-[18px] md:p-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl leading-8 font-semibold tracking-[-0.01em] md:text-[28px] md:leading-9">
            {TEXT.booking.serviceTitle}
          </h1>
          <p className="text-muted">{TEXT.booking.serviceLead}</p>
        </div>
        <label className="flex h-11 w-full items-center gap-2 rounded-control border border-line-strong px-3 focus-within:border-primary md:w-80">
          <SearchIcon size={18} className="shrink-0 text-muted" />
          <span className="sr-only">{TEXT.booking.serviceSearchLabel}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => onSearch(event.target.value)}
            placeholder={TEXT.booking.serviceSearchPlaceholder}
            maxLength={100}
            className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted"
          />
        </label>
      </div>

      {specialties.isError ? <Alert tone="danger">{TEXT.common.genericError}</Alert> : null}

      <div
        role="radiogroup"
        aria-label={TEXT.booking.specialtiesLabel}
        className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-1 md:grid md:grid-cols-3 md:overflow-visible md:pb-0 lg:grid-cols-6"
      >
        {specialties.isPending
          ? Array.from({ length: 6 }, (_, i) => (
              <span
                key={i}
                aria-hidden="true"
                className="h-[150px] shrink-0 basis-[136px] animate-pulse rounded-card bg-divider md:basis-auto"
              />
            ))
          : specialties.data?.map((item) => {
              const checked = !searching && item.id === specialtyId;
              const media = specialtyMedia(item.name);
              return (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={checked}
                  onClick={() => pickSpecialty(item.id)}
                  className={cn(
                    "flex shrink-0 basis-[136px] snap-start flex-col overflow-hidden rounded-card bg-surface text-left md:basis-auto",
                    checked
                      ? "border-2 border-primary bg-[#f4faf9]"
                      : "border border-line hover:border-primary",
                  )}
                >
                  <span className="relative block h-24 w-full bg-[#dce8e7]">
                    <Image
                      src={media.src}
                      alt=""
                      fill
                      sizes="(min-width: 1024px) 180px, 136px"
                      className="object-cover"
                      style={{ objectPosition: media.position }}
                    />
                  </span>
                  <span className="flex flex-col px-3 py-2.5">
                    <span className="flex items-center justify-between gap-1.5">
                      <b className={checked ? "text-primary-ink" : undefined}>{item.name}</b>
                      {checked ? (
                        <span className="flex size-[18px] shrink-0 items-center justify-center rounded-full bg-primary text-white">
                          <CheckIcon size={12} strokeWidth={3} />
                        </span>
                      ) : null}
                    </span>
                    <span className="text-[13px] text-muted">
                      {TEXT.booking.serviceCount(item.service_count)}
                    </span>
                  </span>
                </button>
              );
            })}
      </div>

      <div className="flex flex-col gap-2.5">
        <h2 className="text-[17px] leading-6 font-semibold">
          {searching
            ? TEXT.booking.searchResults(state.q ?? "")
            : specialty
              ? TEXT.booking.servicesOf(specialty.name)
              : TEXT.booking.pickSpecialty}
        </h2>
        {services.isPending && (searching || specialtyId !== undefined) ? (
          <span aria-hidden="true" className="h-[88px] animate-pulse rounded-card bg-divider" />
        ) : null}
        {services.isError ? <Alert tone="danger">{TEXT.common.genericError}</Alert> : null}
        {services.data?.length === 0 ? (
          <p className="rounded-card border border-dashed border-line-strong px-4 py-6 text-center text-muted">
            {TEXT.booking.noServiceFound}
          </p>
        ) : null}
        {services.data?.map((service, index) => (
          <div
            key={service.id}
            className={cn(
              "flex flex-col gap-3 rounded-card px-[18px] py-4 md:flex-row md:flex-wrap md:items-center md:gap-x-5",
              index === 0 ? "border-[1.5px] border-primary bg-[#f4faf9]" : "border border-line",
            )}
          >
            <span className="flex flex-col gap-1 md:min-w-0 md:flex-[1_1_360px]">
              <b>{service.name}</b>
              <span className="text-sm leading-5 text-muted">
                {searching ? `${service.specialty.name} · ` : null}
                {TEXT.booking.scopePrefix}
                {service.scope_description}
              </span>
            </span>
            <span className="flex items-center gap-3 text-sm md:flex-col md:items-end md:gap-0">
              <b>{formatDuration(service.duration_min)}</b>
              <span className="text-muted">{formatPrice(service.ref_price_vnd)}</span>
            </span>
            <Button
              variant={index === 0 ? "primary" : "outline"}
              onClick={() => pickService(service)}
              disabled={service.doctors.length === 0}
              aria-label={`${TEXT.booking.choose} ${service.name}`}
            >
              {TEXT.booking.choose}
            </Button>
          </div>
        ))}
      </div>

      <p className="flex items-center gap-3 rounded-card border border-dashed border-[#9aaaae] px-4 py-3.5">
        <ChatIcon size={22} className="shrink-0 text-primary" />
        <span>
          <b>{TEXT.booking.assistantTitle}</b> {TEXT.booking.assistantBody}{" "}
          <span className="text-muted">{TEXT.home.assistantSoon}</span>
        </span>
      </p>
    </section>
  );
}
