"use client";

// Đăng ký bệnh nhân (G-register, UC01): bắt buộc đồng ý chính sách dữ liệu; lỗi hiện tại đúng ô;
// tạo xong là đăng nhập luôn và quay lại trang đang dở (?next=).
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { api } from "@/shared/api/client";
import { errorMessage, fieldErrors, toApiError } from "@/shared/api/errors";
import { useAuthStore } from "@/shared/auth/auth-store";
import { landingPath, safeNext } from "@/shared/auth/navigation";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Field, FieldError, inputClass, PasswordInput } from "@/shared/ui/field";

import { AuthSplit } from "./auth-split";
import { PasswordMeter } from "./password-meter";
import {
  API_FIELD_TO_FORM,
  formatBirthDateInput,
  normalizePhone,
  parseBirthDate,
  registerSchema,
  type RegisterValues,
} from "./validation";

const T = TEXT.auth;
const GENDERS = ["FEMALE", "MALE", "OTHER"] as const;

export function RegisterScreen() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const status = useAuthStore((state) => state.status);
  const user = useAuthStore((state) => state.user);
  const setSession = useAuthStore((state) => state.setSession);
  const [formError, setFormError] = useState<string | null>(null);
  const [emailTaken, setEmailTaken] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { full_name: "", email: "", phone: "", birth_date: "", password: "" },
  });

  useEffect(() => {
    if (status === "authenticated" && user) router.replace(landingPath(user.role, next));
  }, [status, user, next, router]);

  async function onSubmit(values: RegisterValues) {
    setFormError(null);
    setEmailTaken(false);
    const body = {
      full_name: values.full_name,
      email: values.email,
      phone: normalizePhone(values.phone) ?? values.phone,
      date_of_birth: parseBirthDate(values.birth_date) ?? values.birth_date,
      gender: values.gender,
      password: values.password,
      privacy_consent: values.privacy_consent,
    };
    try {
      const { data, error } = await api.POST("/api/v1/auth/register", { body });
      if (data) {
        setSession(data.access_token, data.user);
        return;
      }
      const apiError = toApiError(error);
      if (apiError.code === "EMAIL_TAKEN") {
        setEmailTaken(true);
        setError("email", { type: "server", message: T.errors.emailTaken }, { shouldFocus: true });
        return;
      }
      const byField = Object.entries(fieldErrors(apiError));
      for (const [field, message] of byField) {
        const formField = API_FIELD_TO_FORM[field];
        if (formField) setError(formField, { type: "server", message });
      }
      if (byField.length === 0) setFormError(errorMessage(apiError));
    } catch {
      setFormError(errorMessage(toApiError(null)));
    }
  }

  const birthDate = register("birth_date");
  const password = useWatch({ control, name: "password" });
  const loginHref = next ? `/login?next=${encodeURIComponent(next)}` : "/login";

  return (
    <AuthSplit
      image="/images/reception.jpg"
      imagePosition="80% 50%"
      title={T.registerPanelTitle}
      points={T.registerPanelPoints}
      wideForm
    >
      <Link href={loginHref} className="self-start text-sm font-medium no-underline">
        {T.backToLogin}
      </Link>
      {next ? <Alert tone="info">{T.continueAfterRegister}</Alert> : null}
      <div className="flex flex-col gap-1">
        <h1 className="text-[30px] leading-[38px] font-bold tracking-[-0.01em]">
          {T.registerTitle}
        </h1>
        <p className="text-muted">{T.registerLead}</p>
      </div>
      {formError ? <Alert tone="danger">{formError}</Alert> : null}

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-3.5">
        <Field label={T.fullName} error={errors.full_name?.message}>
          {({ inputId, describedBy, invalid }) => (
            <input
              id={inputId}
              autoComplete="name"
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              className={inputClass(invalid)}
              {...register("full_name")}
            />
          )}
        </Field>

        <div className="grid gap-3.5 sm:grid-cols-2">
          <Field
            label={T.email}
            error={
              errors.email?.message ? (
                <>
                  {errors.email.message}{" "}
                  {emailTaken ? (
                    <Link href={loginHref} className="font-semibold text-danger">
                      {T.emailTakenLogin}
                    </Link>
                  ) : null}
                </>
              ) : undefined
            }
          >
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
          <Field label={T.phone} hint={T.phoneHint} error={errors.phone?.message}>
            {({ inputId, describedBy, invalid }) => (
              <input
                id={inputId}
                type="tel"
                autoComplete="tel"
                inputMode="tel"
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                className={inputClass(invalid)}
                {...register("phone")}
              />
            )}
          </Field>
        </div>

        <div className="grid gap-3.5 sm:grid-cols-2">
          <Field label={T.birthDate} error={errors.birth_date?.message}>
            {({ inputId, describedBy, invalid }) => (
              <input
                id={inputId}
                inputMode="numeric"
                autoComplete="bday"
                placeholder={T.birthDatePlaceholder}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                className={inputClass(invalid)}
                {...birthDate}
                onChange={(event) => {
                  event.target.value = formatBirthDateInput(event.target.value);
                  void birthDate.onChange(event);
                }}
              />
            )}
          </Field>
          <fieldset className="flex min-w-0 flex-col gap-1.5">
            <legend className="mb-1.5 text-sm font-semibold">{T.gender}</legend>
            <div className="flex gap-1.5">
              {GENDERS.map((gender) => (
                <label
                  key={gender}
                  className={cn(
                    "flex h-12 flex-1 cursor-pointer items-center justify-center rounded-control border border-line-strong bg-surface",
                    "has-checked:border-[1.5px] has-checked:border-primary has-checked:bg-primary-soft has-checked:font-semibold has-checked:text-primary-ink",
                    "has-focus-visible:ring-3 has-focus-visible:ring-primary/30",
                  )}
                >
                  <input type="radio" value={gender} className="sr-only" {...register("gender")} />
                  {T.genders[gender]}
                </label>
              ))}
            </div>
            {errors.gender?.message ? <FieldError>{errors.gender.message}</FieldError> : null}
          </fieldset>
        </div>

        <Field label={T.newPassword} error={errors.password?.message}>
          {({ inputId, describedBy, invalid }) => (
            <span className="flex flex-col gap-2">
              <PasswordInput
                id={inputId}
                autoComplete="new-password"
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("password")}
              />
              <PasswordMeter password={password ?? ""} showHint={!errors.password} />
            </span>
          )}
        </Field>

        <div className="flex flex-col gap-1.5">
          <label
            className={cn(
              "flex cursor-pointer gap-3 rounded-[10px] border bg-surface px-3.5 py-3 text-sm leading-[21px]",
              errors.privacy_consent ? "border-danger" : "border-line-strong",
            )}
          >
            <input
              type="checkbox"
              className="mt-0.5 size-5 shrink-0 accent-primary"
              aria-invalid={errors.privacy_consent ? true : undefined}
              {...register("privacy_consent")}
            />
            <span>
              {T.consentBefore}
              <Link href="/privacy" target="_blank" className="font-semibold">
                {T.consentLink}
              </Link>
              {T.consentAfter} <span className="text-danger">{T.consentRequired}</span>
            </span>
          </label>
          {errors.privacy_consent?.message ? (
            <FieldError>{errors.privacy_consent.message}</FieldError>
          ) : null}
        </div>

        <Button
          type="submit"
          block
          loading={isSubmitting}
          loadingText={T.submitting}
          className="mt-1 h-[50px]"
        >
          {next?.startsWith("/booking") ? T.submitRegisterAndBook : T.submitRegister}
        </Button>
      </form>

      <span className="text-[15px]">
        {T.haveAccount}{" "}
        <Link href={loginHref} className="font-semibold">
          {T.loginLink}
        </Link>
      </span>
    </AuthSplit>
  );
}
