// Client API cho server component: chỉ gọi endpoint CÔNG KHAI, không bao giờ mang token người dùng
// (docs mục 9.1). Đi qua địa chỉ nội bộ API_INTERNAL_URL.
import createClient from "openapi-fetch";

import { getServerEnv } from "@/shared/config/server-env";

import type { paths } from "./schema";

export function serverApi() {
  return createClient<paths>({ baseUrl: getServerEnv().apiInternalUrl });
}
