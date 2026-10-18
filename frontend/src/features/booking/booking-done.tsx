"use client";

// Trang đặt lịch thành công (P-done). Đọc lại lịch hẹn theo ?id= nên tải lại trang vẫn đúng; mã
// lịch hẹn là thứ bệnh nhân cần nhất khi tới quầy lễ tân.
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import type { Appointment } from "@/shared/api/types";
import { appointmentIcs } from "@/shared/appointments/describe";
import { useAppointment } from "@/shared/appointments/queries";
import { useAuthStore } from "@/shared/auth/auth-store";
import { clinicDay, formatDayFull, formatTimeRange } from "@/shared/lib/datetime";
import { CLINIC, TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button, buttonClass } from "@/shared/ui/button";
import { CheckIcon } from "@/shared/ui/icons";

function parseId(value: string | null): number | undefined {
  return value && /^\d+$/.test(value) ? Number(value) : undefined;
}

export function BookingDone() {
  const id = parseId(useSearchParams().get("id"));
  const query = useAppointment(id);
  const email = useAuthStore((s) => s.user?.email);

  if (id === undefined || query.isError) {
    return (
      <main className="mx-auto flex w-full max-w-xl flex-col items-start gap-4 px-4 py-10">
        <Alert tone="warning">{TEXT.booking.doneMissing}</Alert>
        <Link href="/me/appointments" className={buttonClass()}>
          {TEXT.booking.viewMyAppointments}
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-xl flex-col items-center gap-6 px-4 pt-10 pb-28 text-center md:pb-12">
      <span
        aria-hidden="true"
        className="flex size-16 items-center justify-center rounded-full bg-primary-soft text-primary"
      >
        <CheckIcon size={34} strokeWidth={2.5} />
      </span>
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl leading-8 font-semibold md:text-[28px] md:leading-9">
          {TEXT.booking.doneTitle}
        </h1>
        <p className="text-muted">{TEXT.booking.doneLead(email ?? "email của bạn")}</p>
      </div>
      {query.data ? (
        <DoneCard appointment={query.data} />
      ) : (
        <span aria-hidden="true" className="h-72 w-full animate-pulse rounded-card bg-divider" />
      )}
      <div className="flex w-full flex-col gap-3 sm:flex-row sm:justify-center">
        <Link href="/me/appointments" className={buttonClass()}>
          {TEXT.booking.viewMyAppointments}
        </Link>
        <Link href="/booking" className={buttonClass({ variant: "secondary" })}>
          {TEXT.booking.bookAnother}
        </Link>
      </div>
      {query.data ? <IcsLink appointment={query.data} /> : null}
    </main>
  );
}

function DoneCard({ appointment }: { appointment: Appointment }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(appointment.code);
      setCopied(true);
    } catch {
      // Trình duyệt chặn clipboard: mã vẫn hiện rõ để chép tay.
    }
  }

  const rows: [string, string][] = [
    [TEXT.booking.summaryService, appointment.service.name],
    [TEXT.booking.summaryDoctor, appointment.doctor.name],
    ...(CLINIC.address ? [[TEXT.booking.address, CLINIC.address] as [string, string]] : []),
  ];

  return (
    <section className="flex w-full flex-col gap-4 rounded-card border border-line bg-surface p-5 text-left md:p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-sm text-muted">{TEXT.booking.code}</span>
          <span className="font-mono text-2xl font-bold tracking-wide">{appointment.code}</span>
        </div>
        <Button variant="secondary" size="sm" onClick={() => void copy()} aria-live="polite">
          {copied ? TEXT.booking.copied : TEXT.booking.copy}
        </Button>
      </div>
      <div className="flex flex-col rounded-[10px] bg-primary-soft px-4 py-3 text-primary-ink">
        <span className="font-semibold">{formatDayFull(clinicDay(appointment.start_at))}</span>
        <span className="text-xl font-bold tabular-nums">
          {formatTimeRange(appointment.start_at, appointment.end_at)}
        </span>
      </div>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-[15px]">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="border-t border-divider pt-3 text-sm text-muted">{TEXT.booking.arriveEarly}</p>
    </section>
  );
}

function IcsLink({ appointment }: { appointment: Appointment }) {
  function download() {
    const blob = new Blob([appointmentIcs(appointment, CLINIC.name, CLINIC.address)], {
      type: "text/calendar;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${appointment.code}.ics`;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <button
      type="button"
      onClick={download}
      className="text-sm font-semibold text-primary hover:text-primary-hover"
    >
      {TEXT.booking.addToCalendar}
    </button>
  );
}
