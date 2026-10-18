// Chỉ dùng trong client component. Ô lý do khám (tùy chọn, tối đa 500 ký tự như backend). Lý do
// khám là dữ liệu sức khỏe nên chỉ giữ trong bộ nhớ của wizard, không ghi lên URL hay storage.
import { useId } from "react";

import { inputClass } from "@/shared/ui/field";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";

export const REASON_MAX = 500;

export function ReasonField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-semibold">
        {TEXT.booking.reason}{" "}
        <span className="font-normal text-muted">{TEXT.booking.optional}</span>
      </label>
      <textarea
        id={id}
        rows={3}
        maxLength={REASON_MAX}
        value={value}
        placeholder={TEXT.booking.reasonPlaceholder}
        aria-describedby={`${id}-hint`}
        onChange={(event) => onChange(event.target.value)}
        className={cn(inputClass(), "h-auto min-h-[88px] py-3 leading-6")}
      />
      <span
        id={`${id}-hint`}
        className="flex justify-between gap-3 text-[13px] leading-[18px] text-muted"
      >
        <span>{TEXT.booking.reasonHint}</span>
        <span className="tabular-nums">
          {value.length}/{REASON_MAX}
        </span>
      </span>
    </div>
  );
}
