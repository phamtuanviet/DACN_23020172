import type { MetadataRoute } from "next";

import { getServerEnv } from "@/shared/config/server-env";

export const dynamic = "force-dynamic";

// Chỉ production cho phép công cụ tìm kiếm lập chỉ mục; staging và development thì chặn.
export default function robots(): MetadataRoute.Robots {
  const { appEnv, publicBaseUrl } = getServerEnv();
  if (appEnv !== "production") {
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  return {
    rules: { userAgent: "*", allow: ["/", "/services", "/doctors/"], disallow: ["/me/", "/doctor/", "/admin/"] },
    host: publicBaseUrl,
  };
}
