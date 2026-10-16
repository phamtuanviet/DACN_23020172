// Client API cho trình duyệt: cùng origin, gắn access token từ bộ nhớ (docs mục 9.4).
// Gặp 401 thì refresh đúng một lần (các request đồng thời chờ chung lần refresh đó) rồi gửi lại;
// refresh thất bại thì phiên kết thúc, RoleGuard đưa người dùng về trang đăng nhập.
import createClient from "openapi-fetch";

import { useAuthStore } from "@/shared/auth/auth-store";
import { refreshSession } from "@/shared/auth/session";

import type { paths } from "./schema";

// Endpoint tự xử lý 401 của mình (sai mật khẩu, cookie hết hạn), không được kích hoạt refresh.
const NO_REFRESH = ["/api/v1/auth/"];

function withAccessToken(request: Request): Request {
  const token = useAuthStore.getState().accessToken;
  if (!token) return request;
  const headers = new Headers(request.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return new Request(request, { headers });
}

export async function fetchWithRefresh(request: Request): Promise<Response> {
  const retry = request.clone();
  const response = await fetch(withAccessToken(request));
  const path = new URL(request.url, window.location.origin).pathname;
  if (response.status !== 401 || NO_REFRESH.some((prefix) => path.startsWith(prefix))) {
    return response;
  }
  const session = await refreshSession();
  return session ? fetch(withAccessToken(retry)) : response;
}

export const api = createClient<paths>({ baseUrl: "", fetch: fetchWithRefresh });
