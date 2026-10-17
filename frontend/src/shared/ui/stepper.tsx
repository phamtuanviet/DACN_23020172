// Thanh tiến độ của luồng nhiều bước (đặt lịch 4 bước). Bước đã xong hiện lựa chọn của bước đó
// (P-book-2: "Dịch vụ · Khám da liễu tổng quát"); trên điện thoại chỉ bước hiện tại có chữ.
import { cn } from "@/shared/lib/cn";

import { CheckIcon } from "./icons";

export function Stepper({
  steps,
  current,
  details = [],
  label = "Các bước",
}: {
  steps: string[];
  current: number;
  /** Lựa chọn đã có của từng bước, hiện thay cho "Bước N" ở bước đã xong. */
  details?: (string | undefined)[];
  label?: string;
}) {
  return (
    <ol aria-label={label} className="flex gap-2">
      {steps.map((name, index) => {
        const done = index < current;
        const active = index === current;
        const detail = details[index];
        return (
          <li
            key={name}
            aria-current={active ? "step" : undefined}
            className={cn(
              "flex min-w-0 items-center gap-2.5 rounded-[10px] px-2.5 py-2 sm:flex-1 sm:px-3.5 sm:py-2.5",
              active && "flex-1 border-[1.5px] border-primary bg-surface",
              done && "border border-line bg-surface",
              !active && !done && "border border-dashed border-line-strong text-muted",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-bold",
                done && "bg-primary text-white",
                active && "border-2 border-primary text-primary",
                !active && !done && "border-2 border-line-strong",
              )}
            >
              {done ? <CheckIcon size={16} strokeWidth={2.5} /> : index + 1}
            </span>
            <span className={cn("flex min-w-0 flex-col", !active && "max-sm:sr-only")}>
              <span className="text-[13px] leading-[18px] text-muted">
                {done && detail ? name : `Bước ${index + 1}`}
              </span>
              <span className="truncate font-semibold">{done && detail ? detail : name}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
