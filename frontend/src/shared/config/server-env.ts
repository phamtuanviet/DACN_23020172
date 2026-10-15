// Biến môi trường phía server, đọc lúc CHẠY (không phải lúc build), nên cùng một image
// dùng được cho development, staging và production (docs mục 2.4, nguyên tắc 9).
// Không dùng NEXT_PUBLIC_* cho giá trị khác nhau giữa môi trường: chúng bị nhúng cứng lúc build.

export type AppEnv = "development" | "staging" | "production";

export function getServerEnv() {
  return {
    appEnv: (process.env.APP_ENV ?? "development") as AppEnv,
    apiInternalUrl: process.env.API_INTERNAL_URL ?? "http://localhost:8000",
    publicBaseUrl: process.env.PUBLIC_BASE_URL ?? "http://localhost:3000",
    release: process.env.RELEASE ?? "local",
  };
}
