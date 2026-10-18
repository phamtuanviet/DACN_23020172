// Chỉ dùng trong client component. Lịch tháng của bước 3 (P-book-3): ngày tô theo trạng thái thật
// của /availability; ngày nghỉ, hết khung, đã qua hay ngoài 30 ngày (BR-07) không bấm được.
import type { AvailabilityDay } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { formatDayFull, formatMonth, monthGrid } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { ChevronLeftIcon, ChevronRightIcon } from "@/shared/ui/icons";

export function MonthCalendar({
  month,
  days,
  today,
  selected,
  loading,
  canPrev,
  canNext,
  onPrev,
  onNext,
  onSelect,
}: {
  month: string;
  /** Trạng thái từng ngày trong khoảng đặt được của tháng. */
  days: Map<string, AvailabilityDay>;
  today: string;
  selected: string | undefined;
  loading: boolean;
  canPrev: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  onSelect: (day: string) => void;
}) {
  const grid = monthGrid(month);
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onPrev}
          disabled={!canPrev}
          aria-label={TEXT.booking.prevMonth}
          className="flex size-10 items-center justify-center rounded-control border border-line-strong hover:border-primary disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeftIcon size={18} />
        </button>
        <h2 className="text-lg font-semibold" aria-live="polite">
          {formatMonth(month)}
        </h2>
        <button
          type="button"
          onClick={onNext}
          disabled={!canNext}
          aria-label={TEXT.booking.nextMonth}
          className="flex size-10 items-center justify-center rounded-control border border-line-strong hover:border-primary disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronRightIcon size={18} />
        </button>
      </div>

      <div
        role="group"
        aria-label={TEXT.booking.calendarLabel}
        aria-busy={loading || undefined}
        className="grid grid-cols-7 gap-1 text-center"
      >
        {TEXT.booking.weekdays.map((name) => (
          <span key={name} aria-hidden="true" className="py-1 text-xs font-semibold text-muted">
            {name}
          </span>
        ))}
        {Array.from({ length: grid.leading }, (_, i) => (
          <span key={`trong-${i}`} aria-hidden="true" />
        ))}
        {grid.days.map((day) => {
          const info = days.get(day);
          const open = info?.status === "OPEN";
          const isSelected = day === selected;
          const number = Number(day.slice(8));
          const closed = info?.status === "OFF" ? TEXT.booking.dayOff : TEXT.booking.dayFull;
          return (
            <button
              key={day}
              type="button"
              disabled={!open}
              aria-pressed={isSelected}
              aria-label={
                open
                  ? `${formatDayFull(day)}, ${TEXT.booking.slotCount(info.slots.length)}`
                  : info
                    ? `${number}, ${closed}`
                    : String(number)
              }
              onClick={() => onSelect(day)}
              className={cn(
                "relative flex h-10 items-center justify-center rounded-[10px] text-[15px] tabular-nums transition-colors",
                isSelected && "bg-primary font-semibold text-white",
                !isSelected && open && "border border-line font-medium hover:border-primary",
                !open && "text-muted/60",
                loading && "animate-pulse",
              )}
            >
              {number}
              {day === today ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute bottom-1 size-1 rounded-full",
                    isSelected ? "bg-white" : "bg-primary",
                  )}
                />
              ) : null}
            </button>
          );
        })}
      </div>

      <div aria-hidden="true" className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-[4px] border border-line" />
          {TEXT.booking.legendOpen}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-[4px] bg-divider" />
          {TEXT.booking.legendClosed}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-primary" />
          {TEXT.booking.legendToday}
        </span>
      </div>
    </div>
  );
}
