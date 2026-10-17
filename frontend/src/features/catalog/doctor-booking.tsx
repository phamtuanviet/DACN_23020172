"use client";

// Phần tương tác của hồ sơ bác sĩ (G-doctor): chọn dịch vụ (giữ trên URL ?service=) và giờ trống
// 7 ngày tới, tính theo thời lượng của dịch vụ đang chọn. Khung giờ luôn lấy mới (TD-05).
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { AvailabilityDay, DoctorDetail, ServiceBrief } from "@/shared/api/types";
import { bookingHref } from "@/shared/availability/booking-href";
import { useAvailability } from "@/shared/availability/queries";
import { cn } from "@/shared/lib/cn";
import {
  addDays,
  formatDayLong,
  formatDayShort,
  formatTime,
  todayInClinic,
} from "@/shared/lib/datetime";
import { formatDuration, formatPrice } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Button } from "@/shared/ui/button";
import { InfoIcon, RefreshIcon } from "@/shared/ui/icons";

const DAYS = 7;

export function DoctorBooking({ doctor, profile }: { doctor: DoctorDetail; profile: ReactNode }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const requested = Number(searchParams.get("service"));
  const service = doctor.services.find((s) => s.id === requested) ?? doctor.services[0];

  function selectService(id: number) {
    const params = new URLSearchParams(searchParams);
    params.set("service", String(id));
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-4">
        {profile}
        {doctor.services.length > 0 && service ? (
          <ServicePicker
            services={doctor.services}
            selected={service.id}
            onSelect={selectService}
          />
        ) : null}
      </div>
      {service ? (
        <AvailabilityPanel key={service.id} doctor={doctor} service={service} />
      ) : (
        <section className="rounded-card border border-line bg-surface p-6 text-muted">
          {TEXT.catalog.noSlot}
        </section>
      )}
    </div>
  );
}

function ServicePicker({
  services,
  selected,
  onSelect,
}: {
  services: ServiceBrief[];
  selected: number;
  onSelect: (id: number) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2.5 rounded-card border border-line bg-surface px-6 py-5">
      <legend className="float-left mb-1 text-lg leading-[26px] font-semibold">
        {TEXT.doctor.services}
      </legend>
      {services.map((service) => {
        const checked = service.id === selected;
        return (
          <label
            key={service.id}
            className={cn(
              "flex cursor-pointer items-center gap-3 rounded-[10px] px-3.5 py-3",
              checked ? "border-[1.5px] border-primary bg-[#f4faf9]" : "border border-line-strong",
            )}
          >
            <input
              type="radio"
              name="service"
              checked={checked}
              onChange={() => onSelect(service.id)}
              className="size-5 accent-primary"
            />
            <span className="flex flex-1 flex-col">
              <b className="font-semibold">{service.name}</b>
              <span className="text-sm text-muted">
                {formatDuration(service.duration_min)} · {formatPrice(service.ref_price_vnd)}
              </span>
            </span>
          </label>
        );
      })}
      <span className="text-[13px] leading-[19px] text-muted">{TEXT.doctor.servicesHint}</span>
    </fieldset>
  );
}

function dayCaption(day: AvailabilityDay): string {
  if (day.status === "OPEN") return TEXT.availability.slotsCount(day.slots.length);
  return day.status === "OFF" ? TEXT.availability.off : TEXT.availability.full;
}

function periodOf(startAt: string): string {
  const hour = Number(formatTime(startAt).slice(0, 2));
  if (hour < 12) return TEXT.availability.morning;
  return hour < 18 ? TEXT.availability.afternoon : TEXT.availability.evening;
}

function AvailabilityPanel({ doctor, service }: { doctor: DoctorDetail; service: ServiceBrief }) {
  const [today] = useState(todayInClinic);
  const query = useAvailability({
    serviceId: service.id,
    doctorId: doctor.id,
    dateFrom: today,
    dateTo: addDays(today, DAYS - 1),
  });
  const [picked, setPicked] = useState<string | null>(null);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);

  const days = query.data?.days ?? [];
  const active =
    days.find((d) => d.date === picked) ?? days.find((d) => d.status === "OPEN") ?? days[0];

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + days.length) % days.length;
    const day = days[next];
    if (!day) return;
    setPicked(day.date);
    tabs.current[next]?.focus();
  }

  return (
    <section
      aria-labelledby="gio-trong"
      className="flex min-w-0 flex-col gap-[18px] rounded-card border border-line bg-surface p-5 md:p-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1.5">
        <h2 id="gio-trong" className="text-[22px] leading-[30px] font-bold">
          {TEXT.availability.title}
        </h2>
        <span className="text-sm text-muted">
          {service.name} · {formatDuration(service.duration_min)}
        </span>
      </div>

      {query.isPending ? (
        <div aria-hidden="true" className="flex flex-col gap-4">
          <div className="flex gap-2 overflow-hidden">
            {Array.from({ length: DAYS }, (_, i) => (
              <span
                key={i}
                className="h-16 min-w-[88px] flex-1 animate-pulse rounded-[10px] bg-divider"
              />
            ))}
          </div>
          <span className="h-24 animate-pulse rounded-[10px] bg-divider" />
        </div>
      ) : query.isError ? (
        <div className="flex flex-wrap items-center gap-3 rounded-[10px] bg-danger-soft px-4 py-3 text-danger-ink">
          {TEXT.availability.loadError}
          <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
            {TEXT.common.retry}
          </Button>
        </div>
      ) : (
        <>
          <div
            role="tablist"
            aria-label={TEXT.availability.dayTabs}
            className="flex gap-2 overflow-x-auto pb-1 md:grid md:grid-cols-7 md:overflow-visible md:pb-0"
          >
            {days.map((day, index) => {
              const selected = day.date === active?.date;
              const open = day.status === "OPEN";
              return (
                <button
                  key={day.date}
                  ref={(el) => {
                    tabs.current[index] = el;
                  }}
                  type="button"
                  role="tab"
                  id={`ngay-${day.date}`}
                  aria-selected={selected}
                  aria-controls="khung-gio"
                  tabIndex={selected ? 0 : -1}
                  onClick={() => setPicked(day.date)}
                  onKeyDown={(event) => onKeyDown(event, index)}
                  className={cn(
                    "flex h-16 shrink-0 basis-[88px] flex-col items-center justify-center rounded-[10px] text-sm leading-5 md:basis-auto",
                    selected &&
                      "border-2 border-primary bg-primary-soft font-semibold text-primary-ink",
                    !selected && open && "border border-line bg-surface hover:border-primary",
                    !selected && !open && "border border-line bg-ground text-muted",
                  )}
                >
                  <span className="whitespace-nowrap">{formatDayShort(day.date)}</span>
                  <span className={cn("text-xs", !selected && open && "text-muted")}>
                    {dayCaption(day)}
                  </span>
                </button>
              );
            })}
          </div>

          {active ? (
            <DaySlots
              day={active}
              href={(startAt) =>
                bookingHref({
                  specialty: doctor.specialty.id,
                  service: service.id,
                  doctor: doctor.id,
                  date: active.date,
                  start: startAt,
                })
              }
              nearest={query.data.nearest_dates}
              nearestHref={(date) =>
                bookingHref({
                  specialty: doctor.specialty.id,
                  service: service.id,
                  doctor: doctor.id,
                  date,
                })
              }
            />
          ) : null}

          <p className="flex gap-3 rounded-[10px] bg-primary-soft px-4 py-3.5 text-[15px] leading-[22px] text-primary-ink">
            <InfoIcon size={20} className="mt-px shrink-0" />
            {TEXT.availability.pickHint}
          </p>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
            <span>{TEXT.availability.updatedAt(formatTime(new Date(query.dataUpdatedAt)))}</span>
            <Button
              variant="secondary"
              size="sm"
              loading={query.isFetching}
              onClick={() => void query.refetch()}
            >
              <RefreshIcon size={16} />
              {TEXT.availability.reload}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}

function DaySlots({
  day,
  href,
  nearest,
  nearestHref,
}: {
  day: AvailabilityDay;
  href: (startAt: string) => string;
  nearest: string[];
  nearestHref: (date: string) => string;
}) {
  const groups = new Map<string, AvailabilityDay["slots"]>();
  for (const slot of day.slots) {
    const period = periodOf(slot.start_at);
    groups.set(period, [...(groups.get(period) ?? []), slot]);
  }
  return (
    <div
      role="tabpanel"
      id="khung-gio"
      aria-labelledby={`ngay-${day.date}`}
      className="flex flex-col gap-4"
    >
      {groups.size === 0 ? (
        <div className="flex flex-col gap-2 text-muted">
          <span>{TEXT.availability.noSlotsDay}</span>
          {nearest.length > 0 ? (
            <span className="flex flex-wrap items-center gap-2">
              {TEXT.availability.nearest}
              {nearest.map((date) => (
                <Link
                  key={date}
                  href={nearestHref(date)}
                  className="rounded-control border border-primary px-3 py-1.5 font-semibold text-primary-ink hover:bg-primary-soft"
                >
                  {formatDayShort(date)}
                </Link>
              ))}
            </span>
          ) : null}
        </div>
      ) : null}
      {[...groups.entries()].map(([period, slots]) => (
        <div key={period} className="flex flex-col gap-2.5">
          <h3 className="text-[15px] leading-[22px] font-semibold text-muted">
            {formatDayLong(day.date)} · {period}
          </h3>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(88px,1fr))] gap-2">
            {slots.map((slot) => {
              const time = formatTime(slot.start_at);
              return (
                <Link
                  key={slot.start_at}
                  href={href(slot.start_at)}
                  aria-label={TEXT.availability.slotLabel(time, formatDayLong(day.date))}
                  className="flex h-11 items-center justify-center rounded-control border border-primary font-semibold text-primary-ink tabular-nums hover:bg-primary-soft"
                >
                  {time}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
