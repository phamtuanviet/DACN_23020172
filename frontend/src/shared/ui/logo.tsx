import Link from "next/link";

import { cn } from "@/shared/lib/cn";
import { CLINIC } from "@/shared/texts";

// Biểu trưng: ô vuông bo góc màu chính với dấu cộng trắng + tên phòng khám.
export function LogoMark({ size = 32, inverted = false }: { size?: number; inverted?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill={inverted ? "#FFFFFF" : "#0D6B66"} />
      <path
        d="M16 9v14M9 16h14"
        stroke={inverted ? "#0D6B66" : "#FFFFFF"}
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Logo({
  href = "/",
  inverted = false,
  className,
}: {
  href?: string;
  inverted?: boolean;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 font-bold whitespace-nowrap",
        inverted ? "text-white" : "text-ink",
        className,
      )}
    >
      <LogoMark inverted={inverted} />
      <span>{CLINIC.name}</span>
    </Link>
  );
}
