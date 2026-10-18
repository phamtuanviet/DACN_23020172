// Chỉ dùng trong client component. Khung giờ của một ngày, gom theo buổi (P-book-3, P-dialogs):
// dùng chung cho bước 3 của wizard và hộp thoại đổi lịch. Nút bật/tắt (aria-pressed) thay vì liên
// kết vì còn bước xác nhận.
import type { AvailabilitySlot } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { formatTime } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";

export function periodOf(startAt: string): string {
  const hour = Number(formatTime(startAt).slice(0, 2));
  if (hour < 12) return TEXT.availability.morning;
  return hour < 18 ? TEXT.availability.afternoon : TEXT.availability.evening;
}

export function groupByPeriod(slots: AvailabilitySlot[]): [string, AvailabilitySlot[]][] {
  const groups = new Map<string, AvailabilitySlot[]>();
  for (const slot of slots) {
    const period = periodOf(slot.start_at);
    groups.set(period, [...(groups.get(period) ?? []), slot]);
  }
  return [...groups.entries()];
}

export function SlotPicker({
  slots,
  selected,
  onSelect,
  dayLabel,
  disabled,
}: {
  slots: AvailabilitySlot[];
  selected: string | null;
  onSelect: (slot: AvailabilitySlot) => void;
  /** "Thứ Bảy 17/10": đọc kèm giờ cho trình đọc màn hình. */
  dayLabel: string;
  /** Khung không chọn được (ví dụ trùng lịch hiện tại khi đổi lịch). */
  disabled?: (slot: AvailabilitySlot) => boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      {groupByPeriod(slots).map(([period, items]) => (
        <div key={period} className="flex flex-col gap-2.5">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="font-semibold">{period}</h3>
            <span className="text-sm text-muted">{TEXT.booking.slotCount(items.length)}</span>
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(76px,1fr))] gap-2">
            {items.map((slot) => {
              const time = formatTime(slot.start_at);
              const pressed = slot.start_at === selected;
              return (
                <button
                  key={slot.start_at}
                  type="button"
                  aria-pressed={pressed}
                  aria-label={TEXT.availability.slotLabel(time, dayLabel)}
                  disabled={disabled?.(slot)}
                  onClick={() => onSelect(slot)}
                  className={cn(
                    "flex h-11 items-center justify-center rounded-control font-semibold tabular-nums transition-colors",
                    "disabled:cursor-not-allowed disabled:border-line disabled:text-muted disabled:line-through",
                    pressed
                      ? "bg-primary text-white"
                      : "border border-primary text-primary-ink hover:bg-primary-soft",
                  )}
                >
                  {time}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
