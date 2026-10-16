// Kiểm tra dữ liệu đăng ký, đăng nhập phía trình duyệt — cùng quy tắc với backend
// (app/modules/auth/schemas.py) để người dùng thấy lỗi ngay, backend vẫn là nơi quyết định.
import { z } from "zod";

import { TEXT } from "@/shared/texts";

const E = TEXT.auth.errors;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE = /^0\d{9}$/;
const MIN_BIRTH_YEAR = 1900;

/** "0912 345 678", "+84912345678" → "0912345678"; sai định dạng → null. */
export function normalizePhone(value: string): string | null {
  let digits = value.replace(/[\s.\-()]/g, "");
  if (digits.startsWith("+84")) digits = `0${digits.slice(3)}`;
  return PHONE.test(digits) ? digits : null;
}

/** "12/03/1994" → "1994-03-12" nếu là ngày có thật, không ở tương lai; ngược lại null. */
export function parseBirthDate(value: string, today: Date = new Date()): string | null {
  const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;
  const [day, month, year] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  const real =
    date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  const todayUtc = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  if (!real || year < MIN_BIRTH_YEAR || date.getTime() > todayUtc) return null;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** Tự chèn dấu "/" khi gõ ngày sinh: "12031994" → "12/03/1994". */
export function formatBirthDateInput(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join("/");
}

export function meetsPasswordPolicy(password: string): boolean {
  return password.length >= 8 && /\p{L}/u.test(password) && /\d/.test(password);
}

export type PasswordStrength = "weak" | "medium" | "strong";

/** Thước đo hiển thị: đạt chính sách là "trung bình"; dài từ 12 ký tự và đa dạng hơn là "mạnh". */
export function passwordStrength(password: string): PasswordStrength {
  if (!meetsPasswordPolicy(password)) return "weak";
  const extras = [
    password.length >= 12,
    /[A-Z]/.test(password) && /[a-z]/.test(password),
    /[^\p{L}\d]/u.test(password),
  ];
  return extras.filter(Boolean).length >= 2 ? "strong" : "medium";
}

export const loginSchema = z.object({
  email: z.string().trim().min(1, E.required).max(255),
  password: z.string().min(1, E.required).max(128),
});

export const registerSchema = z.object({
  full_name: z.string().trim().min(2, E.nameShort).max(100),
  email: z.string().trim().min(1, E.required).max(255).regex(EMAIL, E.emailInvalid),
  phone: z
    .string()
    .trim()
    .min(1, E.required)
    .refine((value) => normalizePhone(value) !== null, E.phoneInvalid),
  birth_date: z
    .string()
    .trim()
    .min(1, E.required)
    .refine((value) => parseBirthDate(value) !== null, E.birthDateInvalid),
  gender: z.enum(["FEMALE", "MALE", "OTHER"], { error: E.genderRequired }),
  password: z.string().max(128).refine(meetsPasswordPolicy, E.passwordWeak),
  privacy_consent: z.literal(true, { error: E.consentRequired }),
});

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.input<typeof registerSchema>;

// Tên ô trong form khác tên trường API ở đúng một chỗ: ngày sinh.
export const API_FIELD_TO_FORM: Record<string, keyof RegisterValues> = {
  full_name: "full_name",
  email: "email",
  phone: "phone",
  date_of_birth: "birth_date",
  gender: "gender",
  password: "password",
  privacy_consent: "privacy_consent",
};
