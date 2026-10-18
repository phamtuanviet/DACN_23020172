"use client";

// Hồ sơ cá nhân (P-profile, FR-AUTH-06): sửa thông tin trừ email, đổi mật khẩu. Đổi mật khẩu thu
// hồi mọi phiên khác và cấp phiên mới cho thiết bị này (docs mục 4.6), nên lưu lại token mới.
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { api } from "@/shared/api/client";
import { errorMessage, fieldErrors, toApiError } from "@/shared/api/errors";
import type { Me } from "@/shared/api/types";
import { useAuthStore } from "@/shared/auth/auth-store";
import { logout } from "@/shared/auth/session";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Field, FieldError, inputClass, PasswordInput } from "@/shared/ui/field";
import { toast } from "@/shared/ui/toast";

import { loginErrorMessage } from "./login-form";
import { PasswordMeter } from "./password-meter";
import {
  API_FIELD_TO_FORM,
  birthDateInput,
  formatBirthDateInput,
  normalizePhone,
  parseBirthDate,
  passwordChangeSchema,
  profileSchema,
  type PasswordChangeValues,
  type ProfileValues,
} from "./validation";

const T = TEXT.auth;
const P = TEXT.profile;
const GENDERS = ["FEMALE", "MALE", "OTHER"] as const;

export function ProfileScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  async function signOut() {
    await logout();
    router.push("/");
  }

  return (
    <main className="mx-auto grid w-full max-w-[1000px] grid-cols-1 items-start gap-6 px-4 pt-6 pb-28 md:grid-cols-[200px_minmax(0,1fr)] md:px-6 md:pb-12">
      <nav aria-label={P.sectionsLabel} className="flex flex-col gap-1 md:sticky md:top-24">
        <h1 className="mb-2 text-2xl leading-8 font-semibold md:text-[28px] md:leading-9">
          {P.title}
        </h1>
        <div className="flex gap-2 overflow-x-auto md:flex-col md:gap-1">
          {[
            ["#thong-tin", P.info],
            ["#mat-khau", P.password],
            ["#quyen-rieng-tu", P.privacy],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="rounded-control px-3 py-2 text-[15px] font-medium whitespace-nowrap text-ink no-underline hover:bg-primary-soft hover:text-primary-ink"
            >
              {label}
            </a>
          ))}
          <button
            type="button"
            onClick={() => void signOut()}
            className="rounded-control px-3 py-2 text-left text-[15px] font-medium whitespace-nowrap text-danger hover:bg-danger-soft"
          >
            {P.logout}
          </button>
        </div>
      </nav>
      <div className="flex min-w-0 flex-col gap-6">
        {user ? <ProfileForm key={user.id} user={user} /> : null}
        <PasswordForm />
        <section
          id="quyen-rieng-tu"
          className="flex scroll-mt-24 flex-col gap-2 rounded-card border border-line bg-surface p-5 md:p-6"
        >
          <h2 className="text-lg font-semibold">{P.privacy}</h2>
          <p>
            {P.privacyBody}{" "}
            <Link href="/privacy" className="font-semibold">
              {P.privacyLink}
            </Link>
            .
          </p>
          <p className="text-sm text-muted">{P.privacyDelete}</p>
        </section>
      </div>
    </main>
  );
}

function ProfileForm({ user }: { user: Me }) {
  const setUser = useAuthStore((state) => state.setUser);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user.full_name,
      phone: user.phone ?? "",
      birth_date: birthDateInput(user.date_of_birth),
      gender: user.gender ?? undefined,
    },
  });
  const birthDate = register("birth_date");

  async function onSubmit(values: ProfileValues) {
    setFormError(null);
    const { data, error } = await api.PATCH("/api/v1/me", {
      body: {
        full_name: values.full_name,
        phone: normalizePhone(values.phone) ?? values.phone,
        date_of_birth: parseBirthDate(values.birth_date) ?? values.birth_date,
        gender: values.gender,
      },
    });
    if (data) {
      setUser(data);
      reset({
        full_name: data.full_name,
        phone: data.phone ?? "",
        birth_date: birthDateInput(data.date_of_birth),
        gender: data.gender ?? undefined,
      });
      toast.success(P.saved);
      return;
    }
    const apiError = toApiError(error);
    const byField = Object.entries(fieldErrors(apiError));
    for (const [field, message] of byField) {
      const formField = API_FIELD_TO_FORM[field];
      if (formField && formField in profileSchema.shape) {
        setError(formField as keyof ProfileValues, { type: "server", message });
      }
    }
    if (byField.length === 0) setFormError(errorMessage(apiError));
  }

  return (
    <section
      id="thong-tin"
      className="flex scroll-mt-24 flex-col gap-4 rounded-card border border-line bg-surface p-5 md:p-6"
    >
      <h2 className="text-lg font-semibold">{P.info}</h2>
      {formError ? <Alert tone="danger">{formError}</Alert> : null}
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-3.5">
        <div className="grid gap-3.5 sm:grid-cols-2">
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
        <Field label={P.loginEmail} hint={P.emailHint}>
          {({ inputId, describedBy }) => (
            <input
              id={inputId}
              type="email"
              value={user.email}
              readOnly
              aria-describedby={describedBy}
              className={cn(inputClass(), "bg-ground text-muted")}
            />
          )}
        </Field>
        <div className="flex justify-end">
          <Button type="submit" disabled={!isDirty} loading={isSubmitting} loadingText={P.saving}>
            {P.save}
          </Button>
        </div>
      </form>
    </section>
  );
}

function PasswordForm() {
  const setSession = useAuthStore((state) => state.setSession);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<PasswordChangeValues>({
    resolver: zodResolver(passwordChangeSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });
  const newPassword = useWatch({ control, name: "new_password" });

  async function onSubmit(values: PasswordChangeValues) {
    setFormError(null);
    const { data, error } = await api.POST("/api/v1/me/password", {
      body: { current_password: values.current_password, new_password: values.new_password },
    });
    if (data) {
      setSession(data.access_token, data.user);
      reset();
      toast.success(P.passwordChanged);
      return;
    }
    const apiError = toApiError(error);
    const byField = fieldErrors(apiError);
    if (byField.current_password) {
      setError("current_password", { type: "server", message: byField.current_password });
    } else if (byField.new_password) {
      setError("new_password", { type: "server", message: byField.new_password });
    } else {
      setFormError(loginErrorMessage(apiError));
    }
  }

  return (
    <section
      id="mat-khau"
      className="flex scroll-mt-24 flex-col gap-4 rounded-card border border-line bg-surface p-5 md:p-6"
    >
      <h2 className="text-lg font-semibold">{P.changePasswordTitle}</h2>
      {formError ? <Alert tone="danger">{formError}</Alert> : null}
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-3.5">
        <Field label={P.currentPassword} error={errors.current_password?.message}>
          {({ inputId, describedBy, invalid }) => (
            <PasswordInput
              id={inputId}
              autoComplete="current-password"
              aria-describedby={describedBy}
              invalid={invalid}
              {...register("current_password")}
            />
          )}
        </Field>
        <div className="grid gap-3.5 sm:grid-cols-2">
          <Field label={P.newPassword} error={errors.new_password?.message}>
            {({ inputId, describedBy, invalid }) => (
              <span className="flex flex-col gap-2">
                <PasswordInput
                  id={inputId}
                  autoComplete="new-password"
                  aria-describedby={describedBy}
                  invalid={invalid}
                  {...register("new_password")}
                />
                <PasswordMeter password={newPassword ?? ""} showHint={!errors.new_password} />
              </span>
            )}
          </Field>
          <Field label={P.confirmPassword} error={errors.confirm_password?.message}>
            {({ inputId, describedBy, invalid }) => (
              <PasswordInput
                id={inputId}
                autoComplete="new-password"
                aria-describedby={describedBy}
                invalid={invalid}
                {...register("confirm_password")}
              />
            )}
          </Field>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-muted">{P.passwordNote}</span>
          <Button type="submit" loading={isSubmitting} loadingText={P.changingPassword}>
            {P.changePassword}
          </Button>
        </div>
      </form>
    </section>
  );
}
