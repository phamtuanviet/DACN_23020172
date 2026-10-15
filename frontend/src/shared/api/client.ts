// Client API cho trình duyệt: cùng origin, gắn access token từ bộ nhớ (docs mục 9.4).
// Cần làm: khi gặp 401 thì refresh đúng một lần (các request đồng thời chờ chung) rồi gửi lại.
import createClient, { type Middleware } from "openapi-fetch";

import { useAuthStore } from "@/shared/auth/auth-store";

import type { paths } from "./schema";

const attachAccessToken: Middleware = {
  onRequest({ request }) {
    const token = useAuthStore.getState().accessToken;
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: "" });
api.use(attachAccessToken);
