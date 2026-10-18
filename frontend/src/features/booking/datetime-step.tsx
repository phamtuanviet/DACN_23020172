// Chỉ dùng trong client component. Bước 3 (P-book-3, P-book-m): lịch tháng theo khung trống thật,
// khung giờ theo buổi, lý do khám. Ngày đang xem nằm trên URL (?date=); giờ chỉ ghi lên URL khi bấm
// Tiếp tục, vì ?start= là dấu hiệu đã sang bước xác nhận.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { AvailabilityDay, AvailabilitySlot, Service } from "@/shared/api/types";
import { bookingHref, type BookingState } from "@/shared/availability/booking-href";
import { useAvailability } from "@/shared/availability/queries";
import { SlotPicker } from "@/shared/availability/slot-picker";
import {
  addDays,
  addMonths,
  formatDayFull,
  formatDayLong,
  formatDayShort,
  formatTimeRange,
  monthOf,
  todayInClinic,
} from "@/shared/lib/datetime";
import { formatDuration } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button, buttonClass } from "@/shared/ui/button";

import { BookingSummary } from "./booking-summary";
import { MonthCalendar } from "./month-calendar";
import { ReasonField } from "./reason-field";

const WINDOW_DAYS = 30; // BR-07

/** Khoảng ngày đặt được trong một tháng: từ hôm nay tới hết cửa sổ 30 ngày. */
function monthRange(month: string, today: string, lastDay: string) {
  const from = `${month}-01` < today ? today : `${month}-01`;
  const end = addDays(`${addMonths(month, 1)}-01`, -1);
  const to = end > lastDay ? lastDay : end;
  return from <= to ? { from, to } : null;
}

export function DateTimeStep({
  service,
  state,
  doctorName,
  reason,
  onReasonChange,
}: {
  service: Service;
  state: BookingState;
  doctorName?: string;
  reason: string;
  onReasonChange: (value: string) => void;
}) {
  const router = useRouter();
  const [today] = useState(todayInClinic);
  const lastDay = addDays(today, WINDOW_DAYS);
  const [month, setMonth] = useState(() =>
    state.date && state.date >= today && state.date <= lastDay
      ? monthOf(state.date)
      : monthOf(today),
  );
  const [slot, setSlot] = useState<AvailabilitySlot | null>(null);
  const range = monthRange(month, today, lastDay);
  const doctorId = state.doctor === "any" ? null : (state.doctor ?? null);
  const query = useAvailability(
    range ? { serviceId: service.id, doctorId, dateFrom: range.from, dateTo: range.to } : null,
  );

  const days = new Map<string, AvailabilityDay>(
    (query.data?.days ?? []).map((day) => [day.date, day]),
  );
  const isOpen = (day?: string) => Boolean(day && days.get(day)?.status === "OPEN");
  const firstOpen = [...days.values()].find((day) => day.status === "OPEN")?.date;
  const selectedDay =
    state.date && monthOf(state.date) === month && isOpen(state.date) ? state.date : firstOpen;
  const selected = selectedDay ? days.get(selectedDay) : undefined;
  const nearest = query.data?.nearest_dates ?? [];

  function goToMonth(next: string) {
    setMonth(next);
    setSlot(null);
  }

  function selectDay(day: string) {
    setSlot(null);
    if (monthOf(day) !== month) setMonth(monthOf(day));
    router.replace(bookingHref({ ...state, date: day, start: undefined }), { scroll: false });
  }

  function next() {
    if (!slot || !selectedDay) return;
    router.push(bookingHref({ ...state, date: selectedDay, start: slot.start_at }));
  }

  const doctorHref = bookingHref({ specialty: service.specialty.id, service: service.id });
  const chosenText =
    slot && selectedDay
      ? `${formatDayFull(selectedDay)} · ${formatTimeRange(slot.start_at, slot.end_at)}`
      : TEXT.booking.pickSlotFirst;

  return (
    <div className="flex flex-col items-start gap-6 lg:flex-row">
      <section className="flex w-full min-w-0 flex-col gap-5 rounded-card border border-line bg-surface p-[18px] md:p-7 lg:flex-1">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl leading-8 font-semibold tracking-[-0.01em] md:text-[28px] md:leading-9">
            {TEXT.booking.dateTimeTitle}
          </h1>
          <p className="text-muted">
            {service.name} · {formatDuration(service.duration_min)}
            {doctorName ? ` · ${doctorName}` : ""} ·{" "}
            <Link href={doctorHref} className="font-medium text-primary hover:text-primary-hover">
              {TEXT.booking.changeDoctor}
            </Link>
          </p>
        </div>

        {query.isError ? (
          <div className="flex flex-wrap items-center gap-3">
            <Alert tone="danger">{TEXT.availability.loadError}</Alert>
            <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
              {TEXT.common.retry}
            </Button>
          </div>
        ) : null}

        <div className="grid min-w-0 grid-cols-1 gap-6 md:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
          <MonthCalendar
            month={month}
            days={days}
            today={today}
            selected={selectedDay}
            loading={query.isPending}
            canPrev={month > monthOf(today)}
            canNext={month < monthOf(lastDay)}
            onPrev={() => goToMonth(addMonths(month, -1))}
            onNext={() => goToMonth(addMonths(month, 1))}
            onSelect={selectDay}
          />

          <div className="flex min-w-0 flex-col gap-4">
            {query.isPending ? (
              <div aria-hidden="true" className="flex flex-col gap-3">
                <span className="h-7 w-48 animate-pulse rounded bg-divider" />
                <span className="h-28 animate-pulse rounded-[10px] bg-divider" />
              </div>
            ) : selected ? (
              <>
                <h2 className="text-lg font-semibold">{formatDayFull(selected.date)}</h2>
                <SlotPicker
                  slots={selected.slots}
                  selected={slot?.start_at ?? null}
                  onSelect={setSlot}
                  dayLabel={formatDayLong(selected.date)}
                />
              </>
            ) : query.isSuccess ? (
              <div className="flex flex-col gap-2 text-muted">
                <span>{TEXT.booking.noSlotsInMonth}</span>
                {nearest.length > 0 ? (
                  <span className="flex flex-wrap items-center gap-2">
                    {TEXT.booking.nearestDays}
                    {nearest.map((date) => (
                      <button
                        key={date}
                        type="button"
                        onClick={() => selectDay(date)}
                        className="rounded-control border border-primary px-3 py-1.5 font-semibold text-primary-ink hover:bg-primary-soft"
                      >
                        {formatDayShort(date)}
                      </button>
                    ))}
                  </span>
                ) : null}
              </div>
            ) : null}

            <ReasonField value={reason} onChange={onReasonChange} />
          </div>
        </div>

        {/* Điện thoại: thanh dính trên thanh tab, giữ giờ đã chọn và nút Tiếp tục luôn trong tầm tay. */}
        <div className="flex flex-col gap-2 border-t border-divider bg-surface pt-4 max-md:sticky max-md:bottom-16 max-md:z-20 max-md:-mx-[18px] max-md:px-[18px] max-md:pb-3 md:pt-5">
          <span className="text-sm text-muted md:hidden" aria-live="polite">
            {chosenText}
          </span>
          <div className="flex items-center gap-3">
            <Link href={doctorHref} className={buttonClass({ variant: "secondary" })}>
              {TEXT.booking.back}
            </Link>
            <span className="flex-1 text-right text-sm text-muted max-md:hidden">{chosenText}</span>
            <Button onClick={next} disabled={!slot} className="max-md:flex-1">
              {TEXT.booking.nextReview}
            </Button>
          </div>
        </div>
      </section>
      <div className="w-full lg:w-[340px] lg:shrink-0">
        <BookingSummary
          service={service}
          doctorName={doctorName}
          startAt={slot?.start_at}
          note={TEXT.booking.changeDeadline}
        />
      </div>
    </div>
  );
}
