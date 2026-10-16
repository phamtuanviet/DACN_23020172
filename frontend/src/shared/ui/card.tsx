import type { HTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

// Thẻ nền trắng, viền mảnh, bo 12px — khối nội dung cơ bản của hướng A.
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-card border border-line bg-surface", className)} {...props} />;
}
