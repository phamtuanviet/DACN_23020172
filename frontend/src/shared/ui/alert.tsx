// Hộp thông báo trong trang: lỗi (đỏ), cảnh báo (vàng), thông tin (xanh) — kèm biểu tượng và chữ.
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

import { AlertIcon, InfoIcon } from "./icons";

type Tone = "danger" | "warning" | "info";

const TONES: Record<Tone, string> = {
  danger: "border-danger-line bg-danger-soft text-danger-ink",
  warning: "border-amber-line bg-amber-soft text-amber-ink",
  info: "border-transparent bg-primary-soft text-primary-ink",
};

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
}) {
  const Icon = tone === "info" ? InfoIcon : AlertIcon;
  return (
    <div
      role={tone === "info" ? "status" : "alert"}
      className={cn(
        "flex gap-2.5 rounded-[10px] border px-3.5 py-3 text-sm leading-5",
        TONES[tone],
      )}
    >
      <Icon size={18} className="mt-px shrink-0" />
      <div className="flex flex-col gap-0.5">
        {title ? <strong className="font-semibold">{title}</strong> : null}
        <span>{children}</span>
      </div>
    </div>
  );
}
