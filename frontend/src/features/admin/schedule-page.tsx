"use client";

// Ca làm và ngày nghỉ (AD-schedule, UC15, FR-ADM-02): chọn bác sĩ, xem lịch tuần gồm ca lặp hằng
// tuần, ngày nghỉ và số lịch trong từng ca. Tuần đang xem nằm trên URL (?week=YYYY-MM-DD, Thứ Hai).
// Máy tính: lưới 7 ngày × buổi; điện thoại: danh sách theo ngày (docs mục 9.6).
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { errorMessage, toApiError } from "@/shared/api/errors";
import type { Shift, TimeOff } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import {
  addDays,
  clinicDay,
  formatDayShort,
  formatStamp,
  formatWeekRange,
  isoWeekday,
  isValidDay,
  mondayOf,
  todayInClinic,
} from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { inputClass } from "@/shared/ui/field";
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from "@/shared/ui/icons";
import { toast } from "@/shared/ui/toast";

import {
  useAdminAppointments,
  useAdminDoctors,
  useDeleteTimeOff,
  useShifts,
  useTimeOffs,
} from "./queries";
import { ShiftForm, TimeOffForm } from "./schedule-forms";
import { PERIODS, weekPlan, type DayPlan, type Period, type ShiftBlock } from "./schedule-plan";

const T = TEXT.admin;
const PERIOD_LABEL: Record<Period, string> = {
  morning: T.morning,
  afternoon: T.afternoon,
  evening: T.evening,
};

type Panel = { kind: "shift"; shift: Shift | null } | { kind: "time-off" } | null;

export function AdminSchedulePage({ doctorId }: { doctorId?: number }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [today] = useState(todayInClinic);
  const rawWeek = searchParams.get("week");
  const monday = mondayOf(rawWeek && isValidDay(rawWeek) ? rawWeek : today);
  const sunday = addDays(monday, 6);
  const [panel, setPanel] = useState<Panel>(null);

  const doctors = useAdminDoctors();
  const doctor = doctors.data?.find((item) => item.id === doctorId);
  const shifts = useShifts(doctor?.id);
  const timeOffs = useTimeOffs(doctor?.id, monday);
  const appointments = useAdminAppointments({
    doctorId: doctor?.id,
    dateFrom: monday,
    dateTo: sunday,
    page: 1,
    pageSize: 100,
  });
  const removeTimeOff = useDeleteTimeOff();

  // /admin/schedules chưa chọn bác sĩ: mở bác sĩ đầu tiên đang hoạt động.
  const fallback = doctors.data?.find((item) => item.is_active) ?? doctors.data?.[0];
  useEffect(() => {
    if (doctorId === undefined && fallback) router.replace(`/admin/schedules/${fallback.id}`);
  }, [doctorId, fallback, router]);

  function goWeek(next: string) {
    const query = next === mondayOf(today) ? "" : `?week=${next}`;
    router.replace(`${pathname}${query}`, { scroll: false });
  }

  function pickDoctor(id: number) {
    setPanel(null);
    const query = searchParams.toString();
    router.push(`/admin/schedules/${id}${query ? `?${query}` : ""}`);
  }

  const plan =
    shifts.data && timeOffs.data
      ? weekPlan(monday, shifts.data, timeOffs.data, appointments.data?.items ?? [])
      : null;
  const upcoming = (timeOffs.data ?? []).filter((item) => clinicDay(item.end_at) >= today);
  const firstFrom = shifts.data
    ?.map((shift) => shift.valid_from)
    .sort()
    .at(0);

  function deleteTimeOff(item: TimeOff) {
    if (!doctor) return;
    removeTimeOff.mutate(
      { doctorId: doctor.id, timeOffId: item.id },
      {
        onSuccess: () => toast.success(T.timeOffDeleted),
        onError: (error) => toast.error(errorMessage(toApiError(error))),
      },
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-4 px-4 py-6 md:px-7">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold md:text-[26px] md:leading-[34px]">
          {T.scheduleTitle}
        </h1>
        <Button
          size="sm"
          variant="secondary"
          disabled={!doctor}
          onClick={() => setPanel({ kind: "shift", shift: null })}
        >
          <PlusIcon size={16} />
          {T.addShift}
        </Button>
        <Button
          size="sm"
          variant={panel?.kind === "time-off" ? "primary" : "secondary"}
          aria-pressed={panel?.kind === "time-off"}
          disabled={!doctor}
          onClick={() => setPanel({ kind: "time-off" })}
        >
          <PlusIcon size={16} />
          {T.addTimeOff}
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-[240px] flex-col gap-1 text-xs font-semibold text-muted">
          {T.doctor}
          <select
            value={doctor?.id ?? ""}
            onChange={(event) => pickDoctor(Number(event.target.value))}
            className={cn(inputClass(false, "sm"), "font-normal")}
          >
            {doctor ? null : <option value="">{T.pickDoctor}</option>}
            {(doctors.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.specialty.name}
                {item.is_active ? "" : ` (${T.locked.toLowerCase()})`}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label={T.prevWeek}
            onClick={() => goWeek(addDays(monday, -7))}
            className="flex size-10 items-center justify-center rounded-control border border-line-strong bg-surface hover:border-primary"
          >
            <ChevronLeftIcon size={18} />
          </button>
          <span className="min-w-[150px] px-2 text-center font-semibold tabular-nums">
            {formatWeekRange(monday)}
          </span>
          <button
            type="button"
            aria-label={T.nextWeek}
            onClick={() => goWeek(addDays(monday, 7))}
            className="flex size-10 items-center justify-center rounded-control border border-line-strong bg-surface hover:border-primary"
          >
            <ChevronRightIcon size={18} />
          </button>
          {monday !== mondayOf(today) ? (
            <Button size="sm" variant="ghost" onClick={() => goWeek(mondayOf(today))}>
              {T.thisWeek}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          {doctors.isError || shifts.isError || timeOffs.isError ? (
            <Alert tone="danger">{T.loadError}</Alert>
          ) : !doctor || !plan ? (
            <span aria-hidden="true" className="block h-72 animate-pulse rounded-card bg-divider" />
          ) : (
            <>
              <WeekGrid
                plan={plan}
                today={today}
                onPick={(shift) => setPanel({ kind: "shift", shift })}
              />
              <DayList
                plan={plan}
                today={today}
                onPick={(shift) => setPanel({ kind: "shift", shift })}
              />
              <p className="text-sm text-muted">
                {firstFrom ? `${T.validFrom} ${formatDayShort(firstFrom)}. ` : null}
                {T.gridNote}
              </p>
            </>
          )}
          {doctor ? (
            <section className="flex flex-col gap-2 rounded-card border border-line bg-surface p-4">
              <h2 className="font-semibold">{T.timeOffsTitle}</h2>
              {upcoming.length === 0 ? (
                <p className="text-sm text-muted">{T.noTimeOffs}</p>
              ) : (
                <ul className="flex flex-col divide-y divide-divider">
                  {upcoming.map((item) => (
                    <li key={item.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                      <span className="flex-1 tabular-nums">
                        <b>
                          {formatStamp(item.start_at)} – {formatStamp(item.end_at)}
                        </b>
                        {item.reason ? ` · ${item.reason}` : null}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={removeTimeOff.isPending}
                        onClick={() => deleteTimeOff(item)}
                      >
                        {T.deleteTimeOff}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ) : null}
        </div>

        {doctor && panel?.kind === "shift" ? (
          <ShiftForm
            key={panel.shift?.id ?? "new"}
            doctorId={doctor.id}
            shift={panel.shift}
            defaultWeekday={isoWeekday(today)}
            defaultFrom={today}
            onDone={() => setPanel(null)}
          />
        ) : doctor && panel?.kind === "time-off" ? (
          <TimeOffForm
            doctorId={doctor.id}
            defaultDay={addDays(today, 1)}
            onDone={() => setPanel(null)}
          />
        ) : null}
      </div>
    </main>
  );
}

function Block({ block, onPick }: { block: ShiftBlock; onPick: (shift: Shift) => void }) {
  const off = block.off;
  return (
    <button
      type="button"
      onClick={() => onPick(block.shift)}
      aria-label={`${T.editShift}: ${block.start}–${block.end}`}
      className={cn(
        "flex w-full flex-col items-start rounded-[8px] border px-2 py-1.5 text-left text-[13px] leading-[18px]",
        off
          ? "border-amber-line bg-amber-soft text-amber-ink"
          : "border-primary/30 bg-primary-soft text-primary-ink hover:border-primary",
      )}
    >
      <b className="tabular-nums">
        {block.start}–{block.end}
      </b>
      <span>
        {off ? (off.reason ? `${T.dayOff}: ${off.reason}` : T.dayOff) : T.bookedCount(block.booked)}
      </span>
    </button>
  );
}

function OffNote({ day }: { day: DayPlan }) {
  if (day.timeOffs.length === 0) return null;
  return (
    <span className="text-[13px] leading-[18px] font-semibold text-amber">
      {day.timeOffs
        .map((off) => (off.allDay ? T.dayOffAll : `${T.dayOff} ${off.start}–${off.end}`))
        .join(" · ")}
    </span>
  );
}

function WeekGrid({
  plan,
  today,
  onPick,
}: {
  plan: DayPlan[];
  today: string;
  onPick: (shift: Shift) => void;
}) {
  const periods = PERIODS.filter(
    (period) => period !== "evening" || plan.some((day) => day.blocks.evening.length > 0),
  );
  return (
    <div className="hidden overflow-x-auto rounded-card border border-line bg-surface md:block">
      <div className="grid min-w-[760px] grid-cols-[64px_repeat(7,minmax(0,1fr))] text-sm">
        <span className="border-b border-line" />
        {plan.map((day) => (
          <span
            key={day.day}
            className={cn(
              "flex flex-col items-center border-b border-l border-line py-2",
              day.day === today && "bg-primary-soft",
            )}
          >
            <span className="text-xs text-muted">{formatDayShort(day.day).split(" ")[0]}</span>
            <b className="tabular-nums">{formatDayShort(day.day).split(" ")[1]}</b>
            <OffNote day={day} />
          </span>
        ))}
        {periods.map((period) => (
          <div key={period} className="contents">
            <span className="flex items-start justify-center border-b border-line px-1 py-3 text-xs font-semibold text-muted">
              {PERIOD_LABEL[period]}
            </span>
            {plan.map((day) => (
              <div
                key={day.day}
                className="flex min-h-[72px] flex-col gap-1.5 border-b border-l border-line p-1.5"
              >
                {day.blocks[period].length === 0 ? (
                  <span className="m-auto text-xs text-muted">{T.noShift}</span>
                ) : (
                  day.blocks[period].map((block) => (
                    <Block key={block.shift.id} block={block} onPick={onPick} />
                  ))
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function DayList({
  plan,
  today,
  onPick,
}: {
  plan: DayPlan[];
  today: string;
  onPick: (shift: Shift) => void;
}) {
  return (
    <ul className="flex flex-col gap-2 md:hidden">
      {plan.map((day) => {
        const blocks = PERIODS.flatMap((period) => day.blocks[period]);
        return (
          <li
            key={day.day}
            className={cn(
              "flex flex-col gap-2 rounded-card border bg-surface p-3",
              day.day === today ? "border-primary" : "border-line",
            )}
          >
            <div className="flex items-baseline justify-between gap-2">
              <b>{formatDayShort(day.day)}</b>
              <OffNote day={day} />
            </div>
            {blocks.length === 0 ? (
              <span className="text-sm text-muted">{T.noShift}</span>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {blocks.map((block) => (
                  <Block key={block.shift.id} block={block} onPick={onPick} />
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
