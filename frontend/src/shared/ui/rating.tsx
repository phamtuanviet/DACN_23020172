// Điểm đánh giá bác sĩ (FR-RPT-03): hồ sơ bác sĩ, thẻ bác sĩ, đánh giá trong Lịch của tôi.
import { cn } from "@/shared/lib/cn";
import { formatRating } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";

import { StarIcon } from "./icons";

/** "★ 4,8 trên 5 · 36 đánh giá"; `compact`: "★ 4,8 (36)" cho thẻ bác sĩ. Chưa đủ lượt để có điểm
 *  thì chỉ hiện số lượt. */
export function RatingSummary({
  average,
  count,
  compact = false,
  className,
}: {
  average: number | null;
  count: number;
  compact?: boolean;
  className?: string;
}) {
  // `!count`, `== null`: trang công khai cache hồ sơ bác sĩ 5 phút, bản cache cũ có thể chưa có điểm
  if (!count) return <span className={cn("text-muted", className)}>{TEXT.rating.none}</span>;
  if (average == null) {
    return (
      <span className={cn("text-muted", className)}>
        {compact ? TEXT.rating.fewShort(count) : TEXT.rating.few(count)}
      </span>
    );
  }
  const value = formatRating(average);
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span className="sr-only">{TEXT.rating.label(value, count)}</span>
      <StarIcon size={16} className="shrink-0 text-star" />
      <b aria-hidden="true" className="font-semibold">
        {value}
      </b>
      <span aria-hidden="true" className="text-muted">
        {compact ? `(${count})` : TEXT.rating.outOf(count)}
      </span>
    </span>
  );
}

/** Năm sao, tô kín theo số sao đã chấm; chỉ để xem. */
export function Stars({ value, size = 20 }: { value: number; size?: number }) {
  return (
    <span role="img" aria-label={TEXT.rating.stars(value)} className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <StarIcon
          key={n}
          size={size}
          filled={n <= value}
          className={n <= value ? "text-star" : "text-muted"}
        />
      ))}
    </span>
  );
}
