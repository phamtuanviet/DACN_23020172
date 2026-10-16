# Design Direction — Hệ thống đặt lịch khám bệnh tích hợp AI Agent

Oct 16, 2026 · @Viet

Giao diện theo hướng A "Rõ ràng": nền sáng, một màu chính xanh mòng két, chữ to dễ đọc, mỗi màn chỉ một hành động chính. Bản thiết kế 33 màn (khách, bệnh nhân, trợ lý, bác sĩ, quản trị, trạng thái, email) nằm trên [canvas thiết kế](https://claude.ai/artifact/G7KcA8iQpZgU85DMNqyqkM); tài liệu này chốt các quy ước để code bám theo. Token đã nằm trong `frontend/src/app/globals.css`, thành phần trong `frontend/src/shared/ui/`.

## 1. Nguyên tắc

- Người dùng chính là bệnh nhân đặt lịch trên điện thoại (PRD mục 3): thiết kế cho 360 px trước, máy tính sau.
- Một hành động chính mỗi màn, nút chính màu `primary`; hành động phụ là nút viền hoặc liên kết.
- Màu không bao giờ là cách duy nhất để truyền nghĩa: trạng thái luôn có chữ, lỗi luôn có biểu tượng và câu giải thích.
- Khu vực làm việc của bác sĩ và quản trị dùng thanh bên màu tối (`ink`) để phân biệt rõ với khu vực bệnh nhân.

## 2. Màu

| Token | Mã | Dùng cho |
| --- | --- | --- |
| `ground` | #F5F7F8 | Nền trang |
| `surface` | #FFFFFF | Thẻ, ô nhập, đầu trang |
| `ink` | #13262B | Chữ chính; nền thanh bên bác sĩ, quản trị; chân trang |
| `muted` | #51656A | Chữ phụ, gợi ý |
| `line` / `line-strong` | #D9E1E3 / #C9D5D8 | Viền thẻ / viền ô nhập |
| `primary` / `primary-hover` | #0D6B66 / #0A5652 | Nút chính, liên kết, vòng focus |
| `primary-soft` / `primary-ink` | #E3F1EF / #0B5753 | Nền mục đang chọn, hộp thông tin |
| `amber-soft` / `amber-ink` | #FFF3D6 / #6B4400 | Cảnh báo (tài khoản tạm khóa, cần xử lý) |
| `danger` / `danger-soft` | #B42318 / #FEF3F2 | Lỗi, hành động hủy |
| `success` | #1F7A3F | Xác nhận thành công |

Trạng thái lịch hẹn (nền / chữ): Đã đặt #E6EEFB / #1D4E9E · Đã đến #FFF1D6 / #8A5300 · Đã khám #E3F3E8 / #1F6B3A · Đã hủy #EEF1F2 / #4B5A5E · Vắng mặt #FCE8E6 / #A3261C. Biểu đồ của dashboard dùng #0A9488 và #6250D6 (đã qua kiểm tra phân biệt màu), không dùng màu trạng thái.

## 3. Chữ, khoảng cách, bo góc

- Font Be Vietnam Pro (400, 500, 600, 700), tự host qua `next/font` nên hợp CSP `font-src 'self'`.
- Cỡ chữ: tiêu đề trang 28–30 px, tiêu đề mục 24 px, tiêu đề thẻ 17–19 px, chữ thường 16 px, chữ phụ 14 px, chú thích 13 px. Trên điện thoại chữ thường giữ 15–16 px.
- Bo góc: 8 px cho nút và ô nhập (`rounded-control`), 12 px cho thẻ (`rounded-card`).
- Vùng chạm tối thiểu 44 px; ô nhập cao 48 px; nút chính lớn 52 px.
- Vòng focus 2 px màu `primary`, cách 2 px, hiện khi dùng bàn phím.

## 4. Thành phần dùng chung

| Thành phần | File | Ghi chú |
| --- | --- | --- |
| Button, `buttonClass` | `shared/ui/button.tsx` | primary, secondary, ghost, danger; sm, md, lg; trạng thái đang xử lý khóa nút |
| Field, PasswordInput, FieldError | `shared/ui/field.tsx` | Nhãn, gợi ý, lỗi gắn với ô qua `aria-describedby`; nút Hiện/Ẩn mật khẩu |
| Card | `shared/ui/card.tsx` | Nền trắng, viền mảnh, bo 12 px |
| StatusBadge, Badge | `shared/ui/badge.tsx` | Nhãn 5 trạng thái lịch hẹn |
| Alert | `shared/ui/alert.tsx` | Lỗi, cảnh báo, thông tin trong trang |
| Stepper | `shared/ui/stepper.tsx` | 4 bước đặt lịch; điện thoại chỉ hiện chữ của bước hiện tại |
| Dialog | `shared/ui/dialog.tsx` | Dựa trên `<dialog>` gốc: giữ focus, Esc để đóng |
| Toast | `shared/ui/toast.tsx` | Báo kết quả thao tác, tự ẩn sau 4,5 giây |
| SiteHeader, MobileTabBar, SiteFooter | `shared/layout/` | Khu vực khách và bệnh nhân |
| StaffShell | `shared/layout/staff-shell.tsx` | Khu vực bác sĩ và quản trị |

System Design mục 9.2 dự kiến dùng shadcn/ui; Sprint 1 tự viết các thành phần trên bằng Tailwind (không thêm thư viện), API đặt tên gần với shadcn để đổi sau nếu cần.

## 5. Bố cục và responsive

| Chiều rộng | Khách, bệnh nhân | Bác sĩ, quản trị |
| --- | --- | --- |
| Dưới 768 px | Đầu trang gọn (logo, tài khoản); thanh tab dưới đáy: Trang chủ, Đặt lịch, Lịch của tôi, Tài khoản (thêm Trợ lý ở Sprint 4) | Thanh trên màu tối, menu dạng ngăn kéo |
| 768–1023 px | Menu gom vào nút ☰ | Như trên |
| Từ 1024 px | Menu đầy đủ trên đầu trang | Thanh bên cố định rộng 256 px |

- Nội dung rộng tối đa 1200 px, lề 16 px trên điện thoại, 24 px trên máy tính.
- Đăng nhập, đăng ký: ảnh bên trái chỉ hiện từ 1024 px; nhỏ hơn thì chỉ còn biểu mẫu.
- Mọi màn đã kiểm tra ở 1280 px và 390 px; e2e chạy thêm ở 360 px.

## 6. Nội dung và chữ trên giao diện

- Toàn bộ chữ tiếng Việt, gom trong `frontend/src/shared/texts.ts`; tên và số điện thoại phòng khám đổi ở `CLINIC`.
- Thông báo lỗi nói điều cần làm, không nói lỗi kỹ thuật: "Email hoặc mật khẩu không đúng.", "Tài khoản tạm khóa do nhập sai nhiều lần. Thử lại sau 09:27."
- Ngày giờ luôn theo giờ Việt Nam, dạng `Thứ Bảy, 17/10/2026 08:00`.

## 7. Ảnh minh họa

Ảnh nằm trong `frontend/public/images/`, đều từ Pexels ([Pexels License](https://www.pexels.com/license/): dùng miễn phí kể cả thương mại, không bắt buộc ghi công; chân trang vẫn ghi nguồn).

| File | Dùng ở | Tác giả | Nguồn |
| --- | --- | --- | --- |
| hero.jpg | Trang chủ | Cedric Fauntleroy | [pexels.com/photo/4266936](https://www.pexels.com/photo/4266936/) |
| reception.jpg | Đăng ký, thông tin phòng khám | Cedric Fauntleroy | [pexels.com/photo/4266932](https://www.pexels.com/photo/4266932/) |
| clinic.jpg | Thông tin phòng khám | Ivan Babydov | [pexels.com/photo/7789603](https://www.pexels.com/photo/7789603/) |
| assistant.jpg | Giới thiệu trợ lý | RDNE Stock project | [pexels.com/photo/5637528](https://www.pexels.com/photo/5637528/) |
| doctor-tablet.jpg | Đăng nhập | Tima Miroshnichenko | [pexels.com/photo/8376232](https://www.pexels.com/photo/8376232/) |
| spec-derm.jpg | Da liễu | Tima Miroshnichenko | [pexels.com/photo/8376308](https://www.pexels.com/photo/8376308/) |
| spec-internal.jpg | Nội tổng quát | Thirdman | [pexels.com/photo/7659564](https://www.pexels.com/photo/7659564/) |
| spec-pediatrics.jpg | Nhi | Antoni Shkraba | [pexels.com/photo/6749793](https://www.pexels.com/photo/6749793/) |
| spec-ent.jpg | Tai Mũi Họng | Karola G | [pexels.com/photo/5206951](https://www.pexels.com/photo/5206951/) |
| spec-dental.jpg | Răng Hàm Mặt | Nadezhda Moryak | [pexels.com/photo/7803063](https://www.pexels.com/photo/7803063/) |
| spec-eye.jpg | Mắt | Antoni Shkraba | [pexels.com/photo/6749792](https://www.pexels.com/photo/6749792/) |

Ảnh Nhi và Mắt cùng một bé gái và bác sĩ; ảnh trang chủ và lễ tân cùng một bệnh nhân. Nên thay bằng ảnh chụp tại phòng khám khi có.

## 8. Khả năng tiếp cận

- Tương phản chữ thường tối thiểu 4.5:1 trên nền của nó. Đã đo: chữ phụ `muted` trên `ground` 5.7:1, chữ trắng trên nút `primary` 6.3:1, chữ lỗi `danger` trên `danger-soft` 6.1:1, chữ cảnh báo `amber-ink` trên `amber-soft` 7.8:1.
- Biểu tượng luôn `aria-hidden`, nghĩa nằm ở chữ đi kèm hoặc `aria-label` của nút.
- Lỗi của form gắn với ô bằng `aria-invalid` và `aria-describedby`; lỗi chung dùng `role="alert"`.
- Trang yêu cầu đăng nhập hiện khung chờ trong lúc kiểm tra phiên, không lộ nội dung.
