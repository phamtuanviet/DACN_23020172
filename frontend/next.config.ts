import type { NextConfig } from "next";

// Cấu hình chung cho mọi môi trường. Khác biệt giữa development/staging/production
// đến từ biến môi trường lúc chạy (docs mục 9, 11.2), không build riêng cho từng môi trường.
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  output: "standalone",
  // Gắn theo git SHA để trình duyệt đang chạy bản cũ tải lại trang khi gặp server bản mới (docs mục 11.5).
  deploymentId: process.env.RELEASE,
  poweredByHeader: false,
  async rewrites() {
    // Chỉ khi `next dev`: chuyển /api/* tới FastAPI. Ở staging/production Caddy làm việc này.
    if (!isDev) return [];
    const backend = process.env.BACKEND_DEV_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
