// Chỉ dùng trong client component. Bước 4 (P-book-4): xem lại rồi xác nhận đặt lịch. Khung vừa bị
// người khác đặt (409 SLOT_TAKEN) thì giữ nguyên trang, hiện khung gần nhất còn trống để chọn lại
// (UC05 8a, BR-03); khung trống được tải lại cùng lúc.
import Link from "next/link";
import { useRouter } from "next/navigation";

import { errorMessage, toApiError, type ApiError } from "@/shared/api/errors";
import type { Service } from "@/shared/api/types";
import { useBookAppointment } from "@/shared/appointments/queries";
import { useAuthStore } from "@/shared/auth/auth-store";
import { bookingHref, type BookingState } from "@/shared/availability/booking-href";
import {
  clinicDay,
  formatDayFull,
  formatDayLong,
  formatTime,
  formatTimeRange,
} from "@/shared/lib/datetime";
import { formatDuration, formatPhone, formatPrice } from "@/shared/lib/format";
import { CLINIC, TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button, buttonClass } from "@/shared/ui/button";
import { AlertIcon, CheckIcon } from "@/shared/ui/icons";

const DEADLINE_HOURS = 2; // BR-08

export function ConfirmStep({
  service,
  state,
  startAt,
  doctorName,
  reason,
  onBooked,
}: {
  service: Service;
  state: BookingState;
  startAt: string;
  doctorName?: string;
  reason: string;
  onBooked: () => void;
}) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const book = useBookAppointment();
  const error = book.error ? toApiError(book.error) : null;

  const endAt = new Date(Date.parse(startAt) + service.duration_min * 60_000).toISOString();
  const deadline = new Date(Date.parse(startAt) - DEADLINE_HOURS * 3_600_000).toISOString();
  const day = clinicDay(startAt);
  const anyDoctor = state.doctor === "any";
  const stepHref = (overrides: Partial<BookingState>) => bookingHref({ ...state, ...overrides });
  const timeHref = stepHref({ date: day, start: undefined });

  function confirm() {
    book.mutate(
      {
        serviceId: service.id,
        doctorId: typeof state.doctor === "number" ? state.doctor : null,
        startAt,
        reason,
      },
      {
        onSuccess: (appointment) => {
          onBooked();
          router.push(`/booking/done?id=${appointment.id}`);
        },
      },
    );
  }

  const rows: { label: string; value: string; href?: string }[] = [
    {
      label: TEXT.booking.summaryService,
      value: `${service.name} · ${formatDuration(service.duration_min)}`,
      href: bookingHref({ specialty: service.specialty.id }),
    },
    {
      label: TEXT.booking.summaryDoctor,
      value: anyDoctor
        ? TEXT.booking.anyDoctorPicked
        : `${doctorName ?? "…"} · ${service.specialty.name}`,
      href: bookingHref({ specialty: service.specialty.id, service: service.id }),
    },
    {
      label: TEXT.booking.reason,
      value: reason.trim() || TEXT.booking.noReason,
      href: timeHref,
    },
    {
      label: TEXT.booking.patient,
      value: user ? [user.full_name, formatPhone(user.phone)].filter(Boolean).join(" · ") : "…",
      href: "/me/profile",
    },
    {
      label: TEXT.booking.summaryPrice,
      value: `${formatPrice(service.ref_price_vnd)} · ${TEXT.booking.payAtClinic}`,
    },
  ];

  return (
    <div className="flex flex-col items-start gap-6 lg:flex-row">
      <section className="flex w-full min-w-0 flex-col gap-5 rounded-card border border-line bg-surface p-[18px] md:p-7 lg:flex-1">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl leading-8 font-semibold tracking-[-0.01em] md:text-[28px] md:leading-9">
            {TEXT.booking.reviewTitle}
          </h1>
          <p className="text-muted">{TEXT.booking.reviewLead}</p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-card bg-primary-soft px-5 py-4 text-primary-ink">
          <div className="flex flex-col">
            <span className="text-lg font-semibold">{formatDayFull(day)}</span>
            <span className="text-2xl font-bold tabular-nums">
              {formatTimeRange(startAt, endAt)}
            </span>
          </div>
          <Link href={timeHref} className={buttonClass({ variant: "outline", size: "sm" })}>
            {TEXT.booking.changeTime}
          </Link>
        </div>

        <dl className="flex flex-col">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-start gap-3 border-t border-divider py-3 first:border-t-0"
            >
              <div className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:gap-4">
                <dt className="text-sm text-muted sm:w-32 sm:shrink-0 sm:pt-px">{row.label}</dt>
                <dd className="min-w-0 font-medium break-words">{row.value}</dd>
              </div>
              {row.href ? (
                <Link
                  href={row.href}
                  className="shrink-0 text-sm font-semibold text-primary hover:text-primary-hover"
                  aria-label={`${TEXT.booking.edit} ${row.label.toLowerCase()}`}
                >
                  {TEXT.booking.edit}
                </Link>
              ) : null}
            </div>
          ))}
        </dl>

        <p className="flex gap-2.5 rounded-[10px] border border-amber-line bg-amber-soft px-3.5 py-3 text-sm leading-5 text-amber-ink">
          <AlertIcon size={18} className="mt-px shrink-0" />
          <span>
            {TEXT.booking.deadlineNotice(
              `${formatTime(deadline)} ${formatDayLong(clinicDay(deadline))}`,
              CLINIC.phone,
            )}
          </span>
        </p>

        {error ? <BookingError error={error} state={state} timeHref={timeHref} /> : null}

        <div className="flex flex-col-reverse gap-3 border-t border-divider pt-5 sm:flex-row sm:justify-between">
          <Link href={timeHref} className={buttonClass({ variant: "secondary", size: "lg" })}>
            {TEXT.booking.back}
          </Link>
          <Button
            size="lg"
            onClick={confirm}
            loading={book.isPending}
            loadingText={TEXT.booking.confirming}
          >
            {TEXT.booking.confirm}
          </Button>
        </div>
      </section>

      <aside
        aria-label={TEXT.booking.afterTitle}
        className="flex w-full flex-col gap-3 rounded-card border border-line bg-surface p-5 lg:sticky lg:top-24 lg:w-[340px] lg:shrink-0"
      >
        <h2 className="text-lg font-semibold">{TEXT.booking.afterTitle}</h2>
        <ul className="flex flex-col gap-2.5 text-[15px] leading-[22px]">
          {TEXT.booking.afterPoints(user?.email ?? "email của bạn").map((point) => (
            <li key={point} className="flex gap-2.5">
              <CheckIcon size={18} className="mt-0.5 shrink-0 text-primary" />
              {point}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function BookingError({
  error,
  state,
  timeHref,
}: {
  error: ApiError;
  state: BookingState;
  timeHref: string;
}) {
  if (error.code === "SLOT_TAKEN") {
    const alternatives = error.details?.alternatives ?? [];
    return (
      <div className="flex flex-col gap-3">
        <Alert tone="danger">
          {TEXT.booking.slotTaken(state.start ? formatTime(state.start) : "")}
        </Alert>
        {alternatives.length > 0 ? (
          <div className="flex flex-col gap-2">
            <span className="text-sm font-semibold">{TEXT.booking.alternatives}</span>
            <div className="flex flex-wrap gap-2">
              {alternatives.map((alt) => (
                <Link
                  key={`${alt.doctor_id}-${alt.start_at}`}
                  href={bookingHref({
                    ...state,
                    doctor: state.doctor === "any" ? "any" : alt.doctor_id,
                    date: clinicDay(alt.start_at),
                    start: alt.start_at,
                  })}
                  replace
                  className="flex h-11 items-center rounded-control border border-primary px-4 font-semibold text-primary-ink tabular-nums hover:bg-primary-soft"
                >
                  {formatDayLong(clinicDay(alt.start_at))}, {formatTime(alt.start_at)}
                </Link>
              ))}
            </div>
            <span className="text-sm text-muted">{TEXT.booking.slotsReloaded}</span>
          </div>
        ) : (
          <Link href={timeHref} className="self-start font-semibold text-primary">
            {TEXT.booking.pickAgain}
          </Link>
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start gap-2">
      <Alert tone="danger">{errorMessage(error)}</Alert>
      {error.code === "MAX_ACTIVE_APPOINTMENTS" ? (
        <Link href="/me/appointments" className="font-semibold text-primary">
          {TEXT.booking.viewMyAppointments}
        </Link>
      ) : (
        <Link href={timeHref} className="font-semibold text-primary">
          {TEXT.booking.pickAgain}
        </Link>
      )}
    </div>
  );
}
