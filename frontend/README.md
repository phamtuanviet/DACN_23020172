# Frontend

Next.js (App Router), React 19, TypeScript, Tailwind (docs mục 9). Next.js chỉ là lớp giao diện:
không chứa nghiệp vụ, không giữ token, không có API riêng — mọi dữ liệu đến từ FastAPI.

## Code đặt ở đâu

```text
src/
├── app/                 chỉ định tuyến: page, layout, guard theo nhóm vai trò
│   ├── (public)/          trang công khai — server component, tốt cho SEO
│   ├── (auth)/            đăng nhập, đăng ký
│   ├── (patient)/         khu vực bệnh nhân — layout có RoleGuard
│   ├── doctor/  admin/    khu vực bác sĩ, quản trị
│   └── robots.ts  healthz/
├── features/<tên>/      giao diện + logic của một tính năng; bên ngoài chỉ dùng qua index.ts
├── shared/
│   ├── api/               client.ts (trình duyệt), server.ts (server component), schema.d.ts (sinh tự động)
│   ├── auth/  availability/  config/  lib/  ui/
└── proxy.ts             Content-Security-Policy có nonce
```

## Quy tắc

- **`app/` mỏng**: page chỉ ghép component từ `features/`; không viết logic trong page.
- **Feature không import lẫn nhau**; thứ dùng chung đưa lên `shared/`.
- **Server component chỉ gọi API công khai** qua `shared/api/server.ts`; mọi thứ cần đăng nhập là client component dùng `shared/api/client.ts` + TanStack Query.
- **Không dùng** Server Actions, Route Handlers làm API nghiệp vụ hay thư viện xác thực phía Next.js — FastAPI là backend duy nhất.
- **Biến môi trường đọc lúc chạy** qua `shared/config/server-env.ts`. Không dùng `NEXT_PUBLIC_*` cho giá trị khác nhau giữa môi trường (chúng bị nhúng lúc build, trong khi một image chạy cho mọi môi trường).
- **Kiểu API sinh tự động**: không sửa tay `schema.d.ts`; chạy `make api-types` ở thư mục gốc khi backend đổi schema.
- Ngày giờ luôn định dạng qua `shared/lib/datetime.ts` (giờ Việt Nam).

## Lệnh

```bash
npm ci
npm run dev          # http://localhost:3000, /api/* chuyển tới backend :8000
npm run lint && npm run typecheck && npm test
npm run e2e          # Playwright; E2E_BASE_URL=https://staging... để chạy trên staging
```

Thêm component shadcn/ui khi cần: `npx shadcn@latest add button` (đặt vào `src/shared/ui`).
