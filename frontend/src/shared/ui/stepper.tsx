// Thanh tiến độ của luồng nhiều bước (đặt lịch 4 bước). Trên điện thoại chỉ bước hiện tại có chữ.
import { cn } from "@/shared/lib/cn";

import { CheckIcon } from "./icons";

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol aria-label="Các bước" className="flex gap-2">
      {steps.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li
            key={label}
            aria-current={active ? "step" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 sm:flex-1 sm:px-3.5 sm:py-2.5",
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
            <span className={cn("flex flex-col", !active && "max-sm:sr-only")}>
              <span className="text-[13px] leading-[18px] text-muted">Bước {index + 1}</span>
              <span className="font-semibold">{label}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
