"use client";

// Bước 2 (P-book-2): chọn một bác sĩ hoặc "Bác sĩ bất kỳ" (UC05 2a), kèm khung trống sớm nhất của
// từng người. Lựa chọn chỉ ghi lên URL khi bấm Tiếp tục.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import type { EarliestItem, Service } from "@/shared/api/types";
import { bookingHref } from "@/shared/availability/booking-href";
import { useEarliest } from "@/shared/availability/queries";
import { cn } from "@/shared/lib/cn";
import { formatSlotLong } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Avatar } from "@/shared/ui/avatar";
import { Button, buttonClass } from "@/shared/ui/button";
import { UsersIcon } from "@/shared/ui/icons";

import { BookingSummary } from "./booking-summary";
import { useDoctorsOfService } from "./queries";

type Choice = number | "any";

export function DoctorStep({ service }: { service: Service }) {
  const router = useRouter();
  const doctors = useDoctorsOfService(service.id);
  const earliest = useEarliest([service.id], { byDoctor: true });
  const [choice, setChoice] = useState<Choice>("any");

  const list = doctors.data ?? [];
  const chosen = choice === "any" ? undefined : list.find((d) => d.id === choice);
  const firstOf = (doctorId?: number): EarliestItem | undefined =>
    (earliest.data ?? []).find((item) => doctorId === undefined || item.doctor.id === doctorId);

  function next() {
    router.push(
      bookingHref({ specialty: service.specialty.id, service: service.id, doctor: choice }),
    );
  }

  return (
    <div className="flex flex-col items-start gap-6 lg:flex-row">
      <section className="flex w-full min-w-0 flex-col gap-5 rounded-card border border-line bg-surface p-[18px] md:p-7 lg:flex-1">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl leading-8 font-semibold tracking-[-0.01em] md:text-[28px] md:leading-9">
            {TEXT.booking.doctorTitle}
          </h1>
          <p className="text-muted">
            {TEXT.booking.doctorLead(service.name, service.duration_min, service.doctors.length)}
          </p>
        </div>

        {doctors.isError ? <Alert tone="danger">{TEXT.common.genericError}</Alert> : null}
        {doctors.isPending ? (
          <div aria-hidden="true" className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <span key={i} className="h-[82px] animate-pulse rounded-card bg-divider" />
            ))}
          </div>
        ) : null}
        {doctors.isSuccess && list.length === 0 ? (
          <Alert tone="warning">{TEXT.booking.noDoctors}</Alert>
        ) : null}

        {list.length > 0 ? (
          <fieldset className="flex min-w-0 flex-col gap-3">
            <legend className="sr-only">{TEXT.booking.doctorLegend}</legend>
            <DoctorOption
              checked={choice === "any"}
              onSelect={() => setChoice("any")}
              avatar={
                <span
                  aria-hidden="true"
                  className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-ink"
                >
                  <UsersIcon size={22} />
                </span>
              }
              title={TEXT.booking.anyDoctor}
              subtitle={TEXT.booking.anyDoctorHint(list.length)}
              earliest={earliest.isPending ? null : firstOf()}
            />
            {list.map((doctor) => (
              <DoctorOption
                key={doctor.id}
                checked={choice === doctor.id}
                onSelect={() => setChoice(doctor.id)}
                avatar={<Avatar id={doctor.id} name={doctor.name} />}
                title={doctor.name}
                subtitle={`${doctor.specialty.name} · ${TEXT.doctor.genders[doctor.gender]}`}
                profileHref={`/doctors/${doctor.id}?service=${service.id}`}
                earliest={earliest.isPending ? null : firstOf(doctor.id)}
              />
            ))}
          </fieldset>
        ) : null}

        <div className="flex flex-col-reverse gap-3 border-t border-divider pt-5 sm:flex-row sm:justify-between">
          <Link
            href={bookingHref({ specialty: service.specialty.id })}
            className={buttonClass({ variant: "secondary" })}
          >
            {TEXT.booking.back}
          </Link>
          <Button onClick={next} disabled={list.length === 0}>
            {TEXT.booking.nextDateTime}
          </Button>
        </div>
      </section>
      <div className="w-full lg:w-[340px] lg:shrink-0">
        <BookingSummary
          service={service}
          doctorName={choice === "any" ? TEXT.booking.anyDoctor : chosen?.name}
        />
      </div>
    </div>
  );
}

function DoctorOption({
  checked,
  onSelect,
  avatar,
  title,
  subtitle,
  profileHref,
  earliest,
}: {
  checked: boolean;
  onSelect: () => void;
  avatar: ReactNode;
  title: string;
  subtitle: string;
  profileHref?: string;
  /** null: đang tải; undefined: chưa có giờ trống trong 30 ngày. */
  earliest: EarliestItem | null | undefined;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-2 rounded-card px-3.5 py-4 sm:flex-nowrap sm:gap-x-4 sm:px-[18px]",
        checked ? "border-[1.5px] border-primary bg-[#f4faf9]" : "border border-line-strong",
      )}
    >
      <input
        type="radio"
        name="doctor"
        checked={checked}
        onChange={onSelect}
        className="size-5 shrink-0 accent-primary"
      />
      {avatar}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="font-semibold">{title}</span>
        <span className="text-sm leading-5 text-muted">{subtitle}</span>
        {profileHref ? (
          <Link
            href={profileHref}
            className="self-start text-sm leading-5 font-medium text-primary hover:text-primary-hover"
          >
            {TEXT.catalog.viewProfile}
          </Link>
        ) : null}
      </span>
      <span className="flex shrink-0 flex-col text-sm leading-5 max-sm:w-full max-sm:flex-row max-sm:gap-1.5 max-sm:border-t max-sm:border-divider max-sm:pt-2 sm:items-end">
        <span className="text-muted">{TEXT.booking.earliest}</span>
        {earliest === null ? (
          <span className="h-5 w-32 animate-pulse rounded bg-divider" />
        ) : (
          <span className={earliest ? "font-semibold tabular-nums" : "text-muted"}>
            {earliest ? formatSlotLong(earliest.start_at) : TEXT.booking.none}
          </span>
        )}
      </span>
    </label>
  );
}
