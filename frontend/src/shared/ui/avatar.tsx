// Ảnh đại diện bằng chữ viết tắt (chưa có ảnh bác sĩ thật). Màu theo id để mỗi người giữ một màu;
// các cặp màu đều đạt tương phản AA (hướng A, mục khả năng tiếp cận).
import { cn } from "@/shared/lib/cn";
import { initials } from "@/shared/lib/format";

const PALETTES = [
  "bg-primary text-white",
  "bg-[#dce7f7] text-[#1d4e9e]",
  "bg-[#fbebdd] text-[#8a4710]",
  "bg-primary-soft text-primary-ink",
  "bg-[#ece6f6] text-[#4f3a8a]",
];

const SIZES = {
  xs: "size-[30px] text-[11px]",
  sm: "size-10 text-sm",
  md: "size-12 text-base",
  lg: "size-14 text-xl",
  xl: "size-[88px] text-[32px] tracking-[0.02em]",
};

export function Avatar({
  id,
  name,
  size = "md",
  className,
}: {
  id: number;
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-bold",
        PALETTES[id % PALETTES.length],
        SIZES[size],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
