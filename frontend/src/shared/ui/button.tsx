// Nút theo hướng A: cao 44px (vùng chạm đủ lớn trên điện thoại), trạng thái đang xử lý khóa nút để
// tránh bấm đúp (docs mục 9.6). Dùng `buttonClass` cho <Link> trông như nút.
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

import { Spinner } from "./spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-primary text-white hover:bg-primary-hover",
  secondary:
    "border border-line-strong bg-surface text-ink hover:border-primary hover:text-primary-ink",
  ghost: "text-ink hover:bg-primary-soft hover:text-primary-ink",
  danger: "border border-danger bg-surface text-danger hover:bg-danger-soft",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-[18px] text-base",
  lg: "h-[52px] px-6 text-[17px]",
};

export function buttonClass({
  variant = "primary",
  size = "md",
  block = false,
  className,
}: { variant?: ButtonVariant; size?: ButtonSize; block?: boolean; className?: string } = {}) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-control font-semibold whitespace-nowrap transition-colors",
    "disabled:cursor-not-allowed disabled:opacity-60",
    VARIANTS[variant],
    SIZES[size],
    block && "w-full",
    className,
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
  loading?: boolean;
  loadingText?: string;
};

export function Button({
  variant,
  size,
  block,
  loading = false,
  loadingText,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass({ variant, size, block, className })}
      {...props}
    >
      {loading ? <Spinner size={18} /> : null}
      {loading && loadingText ? loadingText : children}
    </button>
  );
}
