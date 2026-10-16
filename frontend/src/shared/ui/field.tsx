// Chỉ dùng trong client component. Ô nhập có nhãn, gợi ý và lỗi gắn với ô (aria-invalid, aria-describedby) theo hướng A.
import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";

import { AlertIcon } from "./icons";

export const inputClass = (invalid?: boolean) =>
  cn(
    "h-12 w-full rounded-control border bg-surface px-3.5 text-base text-ink transition-colors",
    "focus:border-primary focus:ring-3 focus:ring-primary/15 focus:outline-none",
    invalid ? "border-danger border-[1.5px]" : "border-line-strong",
  );

type FieldProps = {
  label: string;
  hint?: ReactNode;
  error?: ReactNode;
  children: (ids: {
    inputId: string;
    describedBy: string | undefined;
    invalid: boolean;
  }) => ReactNode;
};

export function Field({ label, hint, error, children }: FieldProps) {
  const inputId = useId();
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy =
    [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-semibold">
        {label}
      </label>
      {children({ inputId, describedBy, invalid: Boolean(error) })}
      {error ? <FieldError id={errorId}>{error}</FieldError> : null}
      {hint && !error ? (
        <span id={hintId} className="text-[13px] leading-[18px] text-muted">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

export function FieldError({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <span id={id} className="flex gap-1.5 text-[13px] leading-[18px] text-danger">
      <AlertIcon size={15} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </span>
  );
}

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  invalid?: boolean;
};

export function PasswordInput({ invalid, className, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  return (
    <span className="relative block">
      <input
        type={visible ? "text" : "password"}
        className={cn(inputClass(invalid), "pr-16", className)}
        aria-invalid={invalid || undefined}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((value) => !value)}
        aria-label={visible ? TEXT.auth.hidePasswordLabel : TEXT.auth.showPasswordLabel}
        aria-pressed={visible}
        className="absolute top-1 right-1 h-10 rounded-[6px] px-3 text-sm font-semibold text-primary-ink hover:bg-primary-soft"
      >
        {visible ? TEXT.auth.hidePassword : TEXT.auth.showPassword}
      </button>
    </span>
  );
}
