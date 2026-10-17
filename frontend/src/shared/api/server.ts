// Client API cho server component: chỉ gọi endpoint CÔNG KHAI, không bao giờ mang token người dùng
// (docs mục 9.1). Đi qua địa chỉ nội bộ API_INTERNAL_URL.
import createClient from "openapi-fetch";

import { getServerEnv } from "@/shared/config/server-env";

import type { paths } from "./schema";

/** Danh mục ít thay đổi nên được cache 5 phút ở server Next.js; khung trống thì không (TD-05). */
export const CATALOG_REVALIDATE_SECONDS = 300;

export function serverApi() {
  return createClient<paths>({ baseUrl: getServerEnv().apiInternalUrl });
}

/** Chuyên khoa, dịch vụ, bác sĩ: quản trị sửa xong, trang công khai cập nhật sau tối đa 5 phút. */
export function catalogApi() {
  return createClient<paths>({
    baseUrl: getServerEnv().apiInternalUrl,
    fetch: (request) => fetch(request, { next: { revalidate: CATALOG_REVALIDATE_SECONDS } }),
  });
}
