"use client";

// Đăng nhập (G-login, UC02): lỗi không nói rõ sai email hay mật khẩu; khóa tạm hiện giờ mở lại;
// đăng nhập xong về ?next= nếu hợp lệ, không thì về khu vực của vai trò.
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { api } from "@/shared/api/client";
import { errorMessage, toApiError, type ApiError } from "@/shared/api/errors";
import { useAuthStore } from "@/shared/auth/auth-store";
import { landingPath, safeNext } from "@/shared/auth/navigation";
import { formatTime } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Field, inputClass, PasswordInput } from "@/shared/ui/field";

import { AuthSplit } from "./auth-split";
import { loginSchema, type LoginValues } from "./validation";

const T = TEXT.auth;

export function loginErrorMessage(error: ApiError): string {
  switch (error.code) {
    case "UNAUTHENTICATED":
      return T.errors.invalidCredentials;
    case "ACCOUNT_LOCKED":
      return error.details?.locked_until
        ? T.errors.locked(formatTime(error.details.locked_until))
        : error.message;
    case "RATE_LIMITED":
      return T.errors.rateLimited;
    default:
      return errorMessage(error);
  }
}

export function LoginScreen() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const status = useAuthStore((state) => state.status);
  const user = useAuthStore((state) => state.user);
  const setSession = useAuthStore((state) => state.setSession);
  const [formError, setFormError] = useState<ApiError | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  // Đã đăng nhập (kể cả vừa đăng nhập xong) thì không ở lại trang này.
  useEffect(() => {
    if (status === "authenticated" && user) router.replace(landingPath(user.role, next));
  }, [status, user, next, router]);

  async function onSubmit(values: LoginValues) {
    setFormError(null);
    try {
      const { data, error } = await api.POST("/api/v1/auth/login", { body: values });
      if (data) {
        setSession(data.access_token, data.user);
        return;
      }
      setFormError(toApiError(error));
    } catch {
      setFormError(toApiError(null));
    }
  }

  return (
    <AuthSplit
      image="/images/doctor-tablet.jpg"
      imagePosition="50% 40%"
      title={T.loginPanelTitle}
      points={T.loginPanelPoints}
    >
      <Link href="/" className="self-start text-sm font-medium no-underline">
        {T.backHome}
      </Link>
      {next ? <Alert tone="info">{T.continueAfterLogin}</Alert> : null}
      <h1 className="text-[30px] leading-[38px] font-bold tracking-[-0.01em]">{T.loginTitle}</h1>

      {formError ? (
        <Alert tone={formError.code === "UNAUTHENTICATED" ? "danger" : "warning"}>
          {loginErrorMessage(formError)}
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-3.5">
        <Field label={T.email} error={errors.email?.message}>
          {({ inputId, describedBy, invalid }) => (
            <input
              id={inputId}
              type="email"
              autoComplete="email"
              inputMode="email"
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              className={inputClass(invalid)}
              {...register("email")}
            />
          )}
        </Field>
        <Field label={T.password} error={errors.password?.message}>
          {({ inputId, describedBy, invalid }) => (
            <PasswordInput
              id={inputId}
              autoComplete="current-password"
              aria-describedby={describedBy}
              invalid={invalid}
              {...register("password")}
            />
          )}
        </Field>
        <Button
          type="submit"
          block
          loading={isSubmitting}
          loadingText={T.submitting}
          className="mt-1 h-12"
        >
          {T.submitLogin}
        </Button>
      </form>

      <p className="-mt-1 text-sm leading-5 text-muted">{T.forgotPassword}</p>
      <div className="flex flex-col gap-1.5 border-t border-divider pt-4 text-[15px]">
        <span>
          {T.noAccount}{" "}
          <Link
            href={next ? `/register?next=${encodeURIComponent(next)}` : "/register"}
            className="font-semibold"
          >
            {T.registerLink}
          </Link>
        </span>
        <span className="text-[13px] leading-[19px] text-muted">{T.staffNote}</span>
      </div>
    </AuthSplit>
  );
}
