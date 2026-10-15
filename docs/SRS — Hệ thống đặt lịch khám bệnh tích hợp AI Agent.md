# SRS — Hệ thống đặt lịch khám bệnh tích hợp AI Agent

Oct 10, 2026 · @Viet

## 1. Giới thiệu

Tài liệu này đặc tả yêu cầu phần mềm (SRS) phiên bản 1.0 cho hệ thống đặt lịch khám bệnh trực tuyến tích hợp AI Agent, chi tiết hóa PRD 0.1 thành các yêu cầu có thể thiết kế, lập trình và kiểm thử.

**1.1 Mục đích**: làm căn cứ chung cho thiết kế database, API, giao diện, Agent và test case; là tài liệu xin ý kiến giảng viên trước khi viết code.

**1.2 Phạm vi**: một phòng khám, ba vai trò (bệnh nhân, bác sĩ, quản trị viên), kênh web và kênh AI Agent dạng chat. Các nội dung ngoài phạm vi giữ nguyên như mục 4 của PRD (không chẩn đoán, không thanh toán, không nhiều chi nhánh, chỉ dữ liệu giả lập).

**1.3 Quy ước**: yêu cầu dùng từ **"phải"** là bắt buộc; mỗi yêu cầu có mã và mức ưu tiên P0/P1/P2 kế thừa từ PRD.

**1.4 Thuật ngữ**

| Thuật ngữ | Nghĩa |
| --- | --- |
| Ca làm (shift) | Khoảng thời gian bác sĩ làm việc, lặp theo thứ trong tuần, ví dụ thứ Hai 08:00–11:30 |
| Ngày nghỉ (time-off) | Khoảng thời gian bác sĩ không nhận lịch, ghi đè lên ca làm |
| Dịch vụ khám | Loại khám thuộc một chuyên khoa, có thời lượng cố định, ví dụ "Khám da liễu tổng quát – 20 phút" |
| Khung giờ trống (slot) | Khoảng thời gian bắt đầu hợp lệ cho một dịch vụ với một bác sĩ, được tính động, không lưu sẵn |
| Lịch hẹn (appointment) | Một bệnh nhân, một bác sĩ, một dịch vụ, một thời điểm bắt đầu và kết thúc |
| Đề xuất (proposal) | Thao tác đặt/đổi/hủy do Agent chuẩn bị, chờ bệnh nhân xác nhận, có thời hạn |
| Tool | Hàm backend mà Agent được phép gọi |
| Scheduling Engine | Module backend tính khung giờ trống và kiểm tra xung đột |

**1.5 Tài liệu tham chiếu**: PRD 0.1 (10/10/2026); email hướng dẫn đồ án của giảng viên; repository `DACN_23020172`.

## 2. Mô tả tổng quan

Hệ thống là một modular monolith: một backend FastAPI duy nhất phục vụ cả giao diện web lẫn AI Agent, nên mọi quy tắc nghiệp vụ chỉ được cài đặt một lần.

&#91;embedded content: sơ đồ ngữ cảnh · 3 tác nhân, 2 tầng ứng dụng, 3 hệ thống ngoài\]

Agent không truy cập database trực tiếp: tool của nó gọi cùng Scheduling Engine và module lịch hẹn mà giao diện web dùng.

**2.1 Tác nhân**

| Tác nhân | Loại | Quyền hạn chính |
| --- | --- | --- |
| Khách (chưa đăng nhập) | Người | Xem chuyên khoa, dịch vụ, bác sĩ; đăng ký, đăng nhập |
| Bệnh nhân | Người | Đặt/đổi/hủy lịch của mình qua web hoặc Agent; xem lịch sử; đánh giá |
| Bác sĩ | Người | Xem lịch của mình; cập nhật trạng thái, ghi chú |
| Quản trị viên | Người | Quản lý danh mục, ca làm, ngày nghỉ, mọi lịch hẹn; xử lý yêu cầu chuyển nhân viên; xem thống kê |
| AI Agent | Hệ thống nội bộ | Gọi tool đọc dữ liệu và tạo đề xuất, thay mặt bệnh nhân đang đăng nhập |
| Bộ lập lịch nền | Hệ thống nội bộ | Gửi email nhắc lịch, hết hạn đề xuất |
| Dịch vụ LLM | Hệ thống ngoài | Hiểu ngôn ngữ, chọn tool |
| Dịch vụ email (SMTP) | Hệ thống ngoài | Gửi email xác nhận và nhắc lịch |

**2.2 Môi trường vận hành**: trình duyệt Chrome, Edge, Firefox, Safari bản hiện hành, trên desktop và điện thoại (từ 360 px); máy chủ chạy Docker Compose gồm frontend, backend, PostgreSQL 16 và một tiến trình chạy tác vụ nền.

**2.3 Ràng buộc**

- Stack: React + TypeScript + Tailwind, Python FastAPI, PostgreSQL, SQLAlchemy + Alembic, LangGraph hoặc OpenAI Agents SDK.
- Một người phát triển, 8 tuần; ngân sách gọi LLM cá nhân.
- Toàn bộ dữ liệu là dữ liệu giả lập; không lưu thông tin y tế nhạy cảm ngoài ghi chú ngắn của bác sĩ.
- Múi giờ duy nhất Asia/Ho\_Chi\_Minh; ngôn ngữ giao diện và Agent là tiếng Việt.

**2.4 Giả định và phụ thuộc**: có API LLM hỗ trợ tool calling; có tài khoản SMTP thử nghiệm (ví dụ Mailtrap hoặc Gmail app password); giảng viên chấp nhận phạm vi trong PRD.

## 3. Danh sách use case

Hệ thống có 20 use case; 15 use case P0 tạo thành phạm vi bắt buộc của đồ án.

| Mã | Use case | Tác nhân chính | User story (PRD) | Ưu tiên |
| --- | --- | --- | --- | --- |
| UC01 | Đăng ký tài khoản | Khách | US-01 | P0 |
| UC02 | Đăng nhập, đăng xuất | Mọi người dùng | US-01 | P0 |
| UC03 | Tra cứu chuyên khoa, dịch vụ, bác sĩ | Khách, bệnh nhân | US-02 | P0 |
| UC04 | Xem khung giờ trống | Khách, bệnh nhân | US-03 | P0 |
| UC05 | Đặt lịch trên web | Bệnh nhân | US-04 | P0 |
| UC06 | Đổi lịch trên web | Bệnh nhân | US-05 | P0 |
| UC07 | Hủy lịch trên web | Bệnh nhân | US-05 | P0 |
| UC08 | Xem lịch sắp tới và lịch sử | Bệnh nhân | US-06 | P0 |
| UC09 | Đặt lịch qua Agent | Bệnh nhân, AI Agent | US-07, 08, 09, 10 | P0 |
| UC10 | Đổi, hủy lịch qua Agent | Bệnh nhân, AI Agent | US-09 | P0 |
| UC11 | Chuyển yêu cầu sang nhân viên | Bệnh nhân, AI Agent | US-10, 14 | P0 |
| UC12 | Xem lịch khám của bác sĩ | Bác sĩ | US-11 | P0 |
| UC13 | Quản lý chuyên khoa và dịch vụ | Quản trị | US-12 | P0 |
| UC14 | Quản lý bác sĩ | Quản trị | US-12 | P0 |
| UC15 | Quản lý ca làm và ngày nghỉ | Quản trị | US-13 | P0 |
| UC16 | Quản lý lịch hẹn và yêu cầu chuyển nhân viên | Quản trị | US-14 | P0 |
| UC17 | Gửi email xác nhận và nhắc lịch | Bộ lập lịch nền | US-15 | P1 |
| UC18 | Cập nhật trạng thái và ghi chú sau khám | Bác sĩ | US-16 | P1 |
| UC19 | Xem dashboard thống kê | Quản trị | US-17 | P2 |
| UC20 | Đánh giá bác sĩ | Bệnh nhân | US-18 | P2 |

Bốn luồng cốt lõi trong kế hoạch ban đầu tương ứng: đặt lịch thông thường = UC05, đặt qua Agent = UC09, thay đổi lịch = UC06/UC10, quản lý lịch bác sĩ = UC15.

## 4. Đặc tả use case chi tiết

Phần này đặc tả 5 use case có nhiều quy tắc nhất; các use case CRUD còn lại được mô tả đủ qua yêu cầu chức năng ở mục 5.

### UC05 — Đặt lịch trên web

| Thuộc tính | Nội dung |
| --- | --- |
| Tác nhân | Bệnh nhân |
| Tiền điều kiện | Đã đăng nhập; có ít nhất một bác sĩ có ca làm cho dịch vụ được chọn |
| Hậu điều kiện | Một lịch hẹn trạng thái Đã đặt được lưu; khung giờ đó không còn hiện là trống |
| Quy tắc | BR-01, BR-02, BR-03, BR-07, BR-09 |

**Luồng chính**

1. Bệnh nhân chọn chuyên khoa, rồi chọn dịch vụ.
2. Hệ thống hiển thị danh sách bác sĩ thực hiện dịch vụ, kèm lựa chọn "Bác sĩ bất kỳ".
3. Bệnh nhân chọn bác sĩ và một ngày trong 30 ngày tới.
4. Hệ thống tính và hiển thị các khung giờ trống của ngày đó.
5. Bệnh nhân chọn khung giờ, nhập lý do khám (tùy chọn, tối đa 500 ký tự).
6. Hệ thống hiển thị màn hình tóm tắt: dịch vụ, bác sĩ, ngày, giờ bắt đầu–kết thúc.
7. Bệnh nhân bấm Xác nhận.
8. Hệ thống kiểm tra lại khung giờ trong transaction và lưu lịch hẹn.
9. Hệ thống hiển thị mã lịch hẹn và chuyển về danh sách lịch sắp tới.

**Luồng thay thế**

- 2a. Bệnh nhân chọn "Bác sĩ bất kỳ": bước 4 gộp khung giờ trống của mọi bác sĩ thực hiện dịch vụ; khi xác nhận, hệ thống gán bác sĩ còn trống có ít lịch nhất trong ngày.
- 4a. Ngày đã chọn không còn khung trống: hệ thống gợi ý 3 ngày gần nhất còn khung trống.

**Ngoại lệ**

- 8a. Khung giờ vừa bị người khác đặt: không lưu gì, báo "Khung giờ vừa được đặt" và tải lại danh sách khung trống (BR-03).
- 8b. Bệnh nhân đã có lịch trùng giờ hoặc đã đủ 3 lịch đang chờ: từ chối kèm lý do (BR-09).

### UC06 — Đổi lịch trên web

| Thuộc tính | Nội dung |
| --- | --- |
| Tác nhân | Bệnh nhân |
| Tiền điều kiện | Lịch hẹn thuộc bệnh nhân, trạng thái Đã đặt, còn hơn 2 giờ trước giờ khám |
| Hậu điều kiện | Lịch hẹn mang thời điểm mới và giữ nguyên mã; nếu thất bại, lịch cũ không đổi |
| Quy tắc | BR-01, BR-04, BR-05, BR-08 |

**Luồng chính**

1. Bệnh nhân mở lịch hẹn trong danh sách sắp tới, bấm Đổi lịch.
2. Hệ thống hiển thị khung giờ trống cho cùng dịch vụ; mặc định cùng bác sĩ, cho phép chọn bác sĩ khác.
3. Bệnh nhân chọn khung mới; hệ thống hiển thị so sánh cũ → mới.
4. Bệnh nhân bấm Xác nhận.
5. Trong một transaction, hệ thống khóa lịch hẹn, kiểm tra khung mới, cập nhật thời điểm và ghi lịch sử thay đổi.
6. Hệ thống báo thành công.

**Ngoại lệ**

- 1a. Còn dưới 2 giờ trước giờ khám: nút Đổi lịch bị vô hiệu, hiển thị số điện thoại phòng khám (BR-08).
- 5a. Khung mới đã có người đặt: rollback, lịch cũ giữ nguyên, quay lại bước 2 (BR-04).

### UC09 — Đặt lịch qua Agent

| Thuộc tính | Nội dung |
| --- | --- |
| Tác nhân | Bệnh nhân; AI Agent (hệ thống) |
| Tiền điều kiện | Bệnh nhân đã đăng nhập và mở khung chat |
| Hậu điều kiện | Nếu bệnh nhân xác nhận: lịch hẹn được lưu như UC05. Nếu không: không có dữ liệu lịch hẹn nào thay đổi |
| Quy tắc | BR-01 đến BR-03, BR-06, BR-07, BR-09 |

&#91;embedded content: luồng UC09 · 10 bước giữa bệnh nhân, Agent và backend\]

Bước 8 đi thẳng từ giao diện tới backend, không qua Agent: mô hình ngôn ngữ không thể tự xác nhận thay bệnh nhân.

**Luồng chính**

1. Bệnh nhân gửi yêu cầu, ví dụ "Tôi muốn khám da liễu sáng thứ Bảy tuần sau".
2. Agent xác định dịch vụ (gọi `search_services`), đổi mốc thời gian tương đối thành ngày cụ thể (17/10/2026) và buổi (07:00–12:00).
3. Nếu thiếu thông tin bắt buộc (dịch vụ hoặc thời gian), Agent hỏi lại tối đa từng câu một.
4. Agent gọi `find_available_slots` và trình bày tối đa 5 khung phù hợp, kèm tên bác sĩ.
5. Bệnh nhân chọn một khung bằng lời hoặc bằng cách bấm.
6. Agent gọi `propose_booking`; backend tạo đề xuất hết hạn sau 10 phút và giao diện hiển thị thẻ xác nhận ghi rõ ngày, giờ, bác sĩ, dịch vụ.
7. Bệnh nhân bấm Xác nhận trên thẻ.
8. Backend thực hiện như bước 8 của UC05 và đánh dấu đề xuất đã dùng.
9. Agent thông báo kết quả kèm mã lịch hẹn.

**Luồng thay thế**

- 2a. Bệnh nhân mô tả triệu chứng thay vì dịch vụ: Agent nêu rõ không chẩn đoán, liệt kê dịch vụ khớp từ khóa kèm phạm vi khám, hoặc đề nghị chuyển nhân viên (UC11).
- 4a. Không có khung đúng yêu cầu: Agent gợi ý tối đa 3 phương án gần nhất (buổi khác cùng ngày, ngày gần nhất, bác sĩ khác).
- 7a. Bệnh nhân bấm Hủy hoặc không phản hồi quá 10 phút: đề xuất hết hạn, không ghi gì.

**Ngoại lệ**

- 8a. Khung giờ đã bị đặt trong lúc chờ xác nhận: báo lỗi, Agent tự tìm lại khung trống mới (BR-03).
- Tool hoặc LLM lỗi, quá thời gian 30 giây: Agent báo lỗi ngắn và gợi ý dùng giao diện đặt lịch thông thường.

### UC10 — Đổi, hủy lịch qua Agent

Giống UC09, khác ở chỗ: Agent gọi `get_my_appointments` để xác định lịch cần thao tác (hỏi lại nếu có nhiều lịch khớp); đề xuất mang loại `reschedule` hoặc `cancel`; khi xác nhận, backend thực hiện như UC06 hoặc UC07, gồm cả kiểm tra mốc 2 giờ (BR-08).

### UC15 — Quản lý ca làm và ngày nghỉ

| Thuộc tính | Nội dung |
| --- | --- |
| Tác nhân | Quản trị viên |
| Tiền điều kiện | Bác sĩ đã tồn tại |
| Hậu điều kiện | Khung giờ trống của bác sĩ phản ánh ngay ca làm và ngày nghỉ mới |
| Quy tắc | BR-02, BR-10 |

**Luồng chính**

1. Quản trị chọn bác sĩ, mở lịch tuần.
2. Quản trị thêm ca làm: thứ trong tuần, giờ bắt đầu, giờ kết thúc, ngày hiệu lực từ–đến.
3. Hệ thống kiểm tra ca không chồng ca khác của cùng bác sĩ, rồi lưu.
4. Quản trị thêm ngày nghỉ: khoảng thời gian và lý do.
5. Hệ thống liệt kê các lịch hẹn Đã đặt nằm trong khoảng nghỉ, nếu có.
6. Quản trị xác nhận lưu ngày nghỉ; các lịch bị ảnh hưởng được gắn cờ "cần xử lý" để quản trị đổi hoặc hủy từng lịch (BR-10).

**Ngoại lệ**

- 3a. Ca chồng ca đã có, hoặc giờ kết thúc không sau giờ bắt đầu: từ chối, báo lỗi tại trường nhập.
- Xóa hoặc thu hẹp ca làm khi đã có lịch hẹn trong ca: xử lý như ngày nghỉ ở bước 5–6.

## 5. Yêu cầu chức năng

Có 45 yêu cầu chức năng chia theo 8 nhóm; mỗi yêu cầu là một câu kiểm thử được.

### 5.1 Tài khoản và phân quyền (AUTH)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-AUTH-01 | Hệ thống phải cho khách đăng ký bằng họ tên, email, số điện thoại, ngày sinh, giới tính, mật khẩu (tối thiểu 8 ký tự, có chữ và số); email không trùng. | UC01 | P0 |
| FR-AUTH-02 | Hệ thống phải cho đăng nhập bằng email + mật khẩu và cấp access token (hết hạn 30 phút) cùng refresh token (7 ngày). | UC02 | P0 |
| FR-AUTH-03 | Hệ thống phải khóa đăng nhập 15 phút sau 5 lần sai mật khẩu liên tiếp. | UC02 | P0 |
| FR-AUTH-04 | Hệ thống phải phân 3 vai trò PATIENT, DOCTOR, ADMIN và kiểm tra quyền ở mọi API theo BR-05. | Tất cả | P0 |
| FR-AUTH-05 | Tài khoản bác sĩ và quản trị chỉ được tạo bởi quản trị (không tự đăng ký). | UC14 | P0 |
| FR-AUTH-06 | Người dùng phải đổi được mật khẩu và cập nhật thông tin cá nhân (trừ email). | UC02 | P0 |

### 5.2 Danh mục (CAT)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-CAT-01 | Quản trị phải thêm, sửa, ẩn chuyên khoa (tên, mô tả). | UC13 | P0 |
| FR-CAT-02 | Quản trị phải thêm, sửa, ẩn dịch vụ (tên, chuyên khoa, mô tả phạm vi khám, thời lượng 10–120 phút, bội số 5, giá tham khảo). | UC13 | P0 |
| FR-CAT-03 | Quản trị phải gán mỗi bác sĩ vào một chuyên khoa và danh sách dịch vụ bác sĩ thực hiện. | UC14 | P0 |
| FR-CAT-04 | Khách và bệnh nhân phải tìm được dịch vụ, bác sĩ theo từ khóa không dấu và có dấu, lọc theo chuyên khoa. | UC03 | P0 |
| FR-CAT-05 | Danh mục đã có lịch hẹn chỉ được ẩn, không được xóa cứng. | UC13 | P0 |

### 5.3 Scheduling Engine (SCH)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-SCH-01 | Engine phải tính khung trống từ: ca làm hiệu lực, trừ ngày nghỉ, trừ lịch hẹn Đã đặt/Đã đến, theo thời lượng dịch vụ. | UC04 | P0 |
| FR-SCH-02 | Khung giờ bắt đầu từ đầu ca, cách nhau đúng bằng thời lượng dịch vụ; khi gặp một lịch đã đặt, khung kế tiếp bắt đầu ngay sau lịch đó. | UC04 | P0 |
| FR-SCH-03 | Engine phải loại khung đã qua và khung ngoài cửa sổ 30 ngày (BR-07). | UC04 | P0 |
| FR-SCH-04 | Engine phải hỗ trợ truy vấn theo: dịch vụ (bắt buộc), bác sĩ (tùy chọn), khoảng ngày, khoảng giờ trong ngày. | UC04, UC09 | P0 |
| FR-SCH-05 | Engine phải trả về các ngày gần nhất còn khung trống khi ngày được hỏi đã kín. | UC05, UC09 | P0 |
| FR-SCH-06 | Không trùng lịch phải được bảo đảm bằng ràng buộc exclusion trên khoảng thời gian theo bác sĩ trong PostgreSQL. | UC05, UC06 | P0 |

### 5.4 Lịch hẹn (APT)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-APT-01 | Bệnh nhân phải đặt lịch theo UC05; hệ thống sinh mã lịch hẹn dạng `LH-YYMMDD-XXXX`. | UC05 | P0 |
| FR-APT-02 | Bệnh nhân phải đổi lịch theo UC06 trong một transaction (BR-04). | UC06 | P0 |
| FR-APT-03 | Bệnh nhân phải hủy lịch kèm lý do (tùy chọn) khi còn hơn 2 giờ trước giờ khám. | UC07 | P0 |
| FR-APT-04 | Bệnh nhân phải xem danh sách lịch sắp tới và lịch sử, lọc theo trạng thái. | UC08 | P0 |
| FR-APT-05 | Mọi thay đổi trạng thái hoặc thời điểm phải ghi vào lịch sử thay đổi (ai, khi nào, kênh web/Agent, giá trị cũ → mới). | Tất cả | P0 |
| FR-APT-06 | Chuyển trạng thái phải tuân theo sơ đồ ở mục 6.2; chuyển không hợp lệ trả lỗi 409. | Tất cả | P0 |

### 5.5 AI Agent (AGT)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-AGT-01 | Bệnh nhân đã đăng nhập phải mở được khung chat trên mọi trang; lịch sử hội thoại giữ trong phiên. | UC09 | P0 |
| FR-AGT-02 | Agent chỉ được gọi 6 tool đã định nghĩa ở mục 6 của PRD; mọi tool chạy với danh tính bệnh nhân đang đăng nhập. | UC09–11 | P0 |
| FR-AGT-03 | Agent phải chuyển mốc thời gian tương đối thành ngày giờ cụ thể theo múi giờ Asia/Ho\_Chi\_Minh và nhắc lại ngày cụ thể khi đề xuất. | UC09 | P0 |
| FR-AGT-04 | Thao tác ghi chỉ thực hiện qua đề xuất + xác nhận từ giao diện; đề xuất hết hạn sau 10 phút và dùng được một lần (BR-06). | UC09, UC10 | P0 |
| FR-AGT-05 | Agent phải gợi ý tối đa 3 phương án thay thế khi không có khung đúng yêu cầu. | UC09 | P0 |
| FR-AGT-06 | Agent không chẩn đoán và không suy luận chuyên khoa từ triệu chứng; khi gặp triệu chứng phải nêu giới hạn và đưa lựa chọn tìm dịch vụ hoặc chuyển nhân viên. | UC09, UC11 | P0 |
| FR-AGT-07 | `handoff_to_staff` phải tạo yêu cầu hỗ trợ gồm tóm tắt hội thoại, hiện trong hàng chờ của quản trị. | UC11 | P0 |
| FR-AGT-08 | Mỗi lượt gọi tool phải được ghi log: hội thoại, tool, tham số, kết quả, thời gian xử lý. | UC09–11 | P0 |
| FR-AGT-09 | Mỗi bệnh nhân tối đa 50 tin nhắn gửi Agent mỗi ngày. | UC09 | P0 |

### 5.6 Bác sĩ (DOC)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-DOC-01 | Bác sĩ phải xem lịch khám của mình theo ngày và tuần, gồm tên bệnh nhân, tuổi, dịch vụ, giờ, lý do khám. | UC12 | P0 |
| FR-DOC-02 | Bác sĩ phải cập nhật trạng thái Đã đến, Đã khám, Vắng mặt cho lịch trong ngày. | UC18 | P1 |
| FR-DOC-03 | Bác sĩ phải lưu ghi chú sau khám tối đa 1.000 ký tự; bệnh nhân xem được ghi chú của lịch mình. | UC18 | P1 |

### 5.7 Quản trị (ADM)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-ADM-01 | Quản trị phải tạo, sửa, khóa tài khoản bác sĩ. | UC14 | P0 |
| FR-ADM-02 | Quản trị phải quản lý ca làm và ngày nghỉ theo UC15. | UC15 | P0 |
| FR-ADM-03 | Quản trị phải xem, lọc (ngày, bác sĩ, trạng thái, kênh) và đổi/hủy mọi lịch hẹn, không bị giới hạn mốc 2 giờ. | UC16 | P0 |
| FR-ADM-04 | Quản trị phải xem hàng chờ yêu cầu chuyển nhân viên và lịch "cần xử lý", đánh dấu đã xử lý. | UC16 | P0 |

### 5.8 Thông báo, thống kê, đánh giá (NTF, RPT)

| Mã | Yêu cầu | UC | Ưu tiên |
| --- | --- | --- | --- |
| FR-NTF-01 | Hệ thống phải gửi email cho bệnh nhân sau khi đặt, đổi, hủy lịch (kể cả do quản trị thực hiện). | UC17 | P1 |
| FR-NTF-02 | Hệ thống phải gửi email nhắc 24 giờ trước giờ khám, mỗi lịch một lần. | UC17 | P1 |
| FR-NTF-03 | Gửi email lỗi không được làm hỏng thao tác đặt lịch; email lỗi được thử lại tối đa 3 lần. | UC17 | P1 |
| FR-RPT-01 | Dashboard phải hiển thị: số lịch theo ngày (30 ngày), tỷ lệ hủy, tỷ lệ vắng mặt, số lịch theo bác sĩ, tỷ lệ đặt qua web và Agent. | UC19 | P2 |
| FR-RPT-02 | Bệnh nhân phải đánh giá 1–5 sao và nhận xét tối đa 500 ký tự cho lịch Đã khám, một lần mỗi lịch. | UC20 | P2 |
| FR-RPT-03 | Trang bác sĩ phải hiện điểm trung bình và số lượt đánh giá. | UC20 | P2 |

## 6. Yêu cầu dữ liệu

Mô hình dữ liệu khái niệm gồm 16 thực thể; ERD chi tiết (kiểu cột, chỉ mục) sẽ nằm ở `docs/database/erd.md`.

### 6.1 Thực thể chính

| Thực thể | Thuộc tính chính | Ghi chú |
| --- | --- | --- |
| User | id, email, password\_hash, role, full\_name, phone, is\_active | Dùng chung cho 3 vai trò |
| PatientProfile | user\_id, date\_of\_birth, gender | 1–1 với User vai trò PATIENT |
| Doctor | user\_id, specialty\_id, title, bio, gender | 1–1 với User vai trò DOCTOR |
| Specialty | id, name, description, is\_active |  |
| Service | id, specialty\_id, name, scope\_description, duration\_min, ref\_price, is\_active | `scope_description` dùng cho Agent |
| DoctorService | doctor\_id, service\_id | Bác sĩ thực hiện dịch vụ nào |
| Shift | id, doctor\_id, weekday, start\_time, end\_time, valid\_from, valid\_to | Ca lặp hằng tuần |
| TimeOff | id, doctor\_id, start\_at, end\_at, reason |  |
| Appointment | id, code, patient\_id, doctor\_id, service\_id, start\_at, end\_at, status, reason, channel (WEB/AGENT), needs\_attention, doctor\_note | Exclusion constraint (doctor\_id, \[start\_at, end\_at)) khi status đang hiệu lực |
| AppointmentHistory | id, appointment\_id, actor\_id, channel, action, old\_value, new\_value, created\_at | Nhật ký thay đổi |
| AgentProposal | id, conversation\_id, patient\_id, type (BOOK/RESCHEDULE/CANCEL), payload, expires\_at, status | Dùng một lần |
| Conversation, Message | id, patient\_id, role, content, created\_at | Lịch sử chat |
| ToolCallLog | id, conversation\_id, tool\_name, args, result, latency\_ms, created\_at | Phục vụ đánh giá Agent |
| SupportRequest | id, patient\_id, conversation\_id, summary, status, handled\_by | Từ `handoff_to_staff` |
| Review | id, appointment\_id, rating, comment | P2, 1–1 với lịch Đã khám |

### 6.2 Trạng thái lịch hẹn

&#91;embedded content: trạng thái lịch hẹn · 5 trạng thái, 6 chuyển đổi\]

Mọi chuyển đổi khác (ví dụ Đã hủy → Đã đặt) bị từ chối với mã 409 (FR-APT-06); khi lịch chuyển sang Đã hủy hoặc Vắng mặt, khung giờ được trả lại.

### 6.3 Quy định dữ liệu

- Mọi thời điểm lưu kiểu `timestamptz`; hiển thị theo Asia/Ho\_Chi\_Minh.
- Danh mục và tài khoản dùng xóa mềm (`is_active`); lịch hẹn không bao giờ bị xóa.
- Dữ liệu mẫu (seed): 6 chuyên khoa, khoảng 20 dịch vụ, 20 bác sĩ, 50 bệnh nhân giả, ca làm 4 tuần, khoảng 300 lịch hẹn.

## 7. Yêu cầu giao diện ngoài

Giao diện gồm 16 màn hình, một REST API dùng chung cho web và Agent, cùng hai kết nối ra ngoài là LLM và SMTP.

### 7.1 Màn hình

| Vai trò | Màn hình |
| --- | --- |
| Khách | Trang chủ + tìm kiếm; Danh sách chuyên khoa/dịch vụ; Hồ sơ bác sĩ; Đăng ký; Đăng nhập |
| Bệnh nhân | Đặt lịch (chọn dịch vụ → bác sĩ → ngày → giờ → xác nhận); Lịch của tôi (sắp tới, lịch sử, đổi, hủy); Hồ sơ cá nhân; Khung chat Agent (nổi trên mọi trang, có thẻ xác nhận) |
| Bác sĩ | Lịch khám ngày/tuần; Chi tiết lịch hẹn (trạng thái, ghi chú) |
| Quản trị | Danh mục (chuyên khoa, dịch vụ); Bác sĩ; Ca làm và ngày nghỉ (dạng lịch tuần); Lịch hẹn + hàng chờ cần xử lý; Dashboard |

Yêu cầu chung: responsive từ 360 px; mọi thao tác ghi có trạng thái đang xử lý và thông báo kết quả; lỗi hiển thị bằng tiếng Việt, không lộ thông tin kỹ thuật.

### 7.2 REST API

API theo chuẩn REST, JSON, tiền tố `/api/v1`, tài liệu OpenAPI tự sinh tại `/docs`. Lỗi trả dạng `{code, message, details}` với mã HTTP 400, 401, 403, 404, 409, 422, 429.

| Nhóm | Endpoint chính |
| --- | --- |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET/PATCH /me` |
| Danh mục | `GET /specialties`, `GET /services?q=&specialty_id=`, `GET /doctors?q=&service_id=`, CRUD dưới `/admin/...` |
| Khung trống | `GET /availability?service_id=&doctor_id=&date_from=&date_to=&time_from=&time_to=` |
| Lịch hẹn | `POST /appointments`, `GET /appointments/me`, `PATCH /appointments/{id}/reschedule`, `POST /appointments/{id}/cancel`, `PATCH /appointments/{id}/status` |
| Lịch bác sĩ | `GET/POST/PATCH/DELETE /admin/doctors/{id}/shifts`, `.../time-offs`, `GET /doctor/schedule?from=&to=` |
| Agent | `POST /agent/chat` (trả lời dạng stream), `POST /agent/proposals/{id}/confirm`, `POST /agent/proposals/{id}/reject` |
| Quản trị | `GET /admin/appointments`, `GET/PATCH /admin/support-requests`, `GET /admin/stats` |

Tool của Agent là lớp mỏng gọi đúng các service backend phía sau những endpoint trên, không truy cập database trực tiếp.

### 7.3 Giao diện LLM

- Gọi qua SDK của nhà cung cấp, hỗ trợ tool calling; tên mô hình và API key cấu hình bằng biến môi trường.
- Thời gian chờ tối đa 30 giây mỗi lượt, thử lại 1 lần khi lỗi mạng.
- Prompt hệ thống chứa: ngày giờ hiện tại, múi giờ, giới hạn hành vi, danh sách tool; không chứa dữ liệu bệnh nhân khác.

### 7.4 Giao diện email (P1)

Gửi qua SMTP cấu hình bằng biến môi trường; mẫu email HTML tiếng Việt cho 4 loại: xác nhận đặt, xác nhận đổi, xác nhận hủy, nhắc lịch.

## 8. Yêu cầu phi chức năng

Mỗi yêu cầu có cách đo cụ thể để kiểm chứng ở tuần 7.

| Mã | Nhóm | Yêu cầu | Cách đo |
| --- | --- | --- | --- |
| NFR-01 | Hiệu năng | API `/availability` p95 < 500 ms với dữ liệu seed | Locust hoặc k6, 20 người dùng ảo, 5 phút |
| NFR-02 | Hiệu năng | Các API đọc khác p95 < 300 ms | Như NFR-01 |
| NFR-03 | Hiệu năng | Agent trả token đầu tiên < 5 s, hoàn tất một lượt < 15 s (p90) | Từ ToolCallLog và log thời gian chat |
| NFR-04 | Đồng thời | 20 yêu cầu đặt cùng khung giờ → đúng 1 lịch hẹn | Test pytest chạy song song |
| NFR-05 | Bảo mật | Mật khẩu băm bằng argon2 hoặc bcrypt; không có secret trong repo | Review code + gitleaks trên CI |
| NFR-06 | Bảo mật | Mọi endpoint cần đăng nhập trả 401 khi thiếu token, 403 khi sai quyền | Test tự động duyệt toàn bộ route |
| NFR-07 | Bảo mật | Giới hạn tốc độ: đăng nhập 10 lần/phút/IP; Agent theo FR-AGT-09 | Test trả 429 |
| NFR-08 | An toàn Agent | 0 thao tác ghi khi chưa xác nhận; 0 lần truy cập dữ liệu bệnh nhân khác | Bộ kịch bản đánh giá Agent, gồm kịch bản tấn công prompt injection |
| NFR-09 | Toàn vẹn | Đặt, đổi, hủy là nguyên tử; không có lịch hẹn mồ côi sau lỗi giữa chừng | Test giả lập lỗi trong transaction |
| NFR-10 | Khả dụng | Bệnh nhân mới đặt được lịch đầu tiên trên web trong ≤ 3 phút không cần hướng dẫn | Thử nghiệm với 5–10 người |
| NFR-11 | Tương thích | Giao diện dùng được ở chiều rộng 360 px trên Chrome, Safari di động | Playwright, viewport di động |
| NFR-12 | Khả năng bảo trì | Độ phủ test ≥ 70% cho Scheduling Engine và module lịch hẹn; lint và type check pass trên CI | Báo cáo coverage, GitHub Actions |
| NFR-13 | Triển khai | `docker compose up` dựng toàn hệ thống + seed trong ≤ 5 phút trên máy mới | Thử trên máy sạch |
| NFR-14 | Quan sát | Log có request id; lỗi 5xx ghi kèm stack trace | Kiểm tra log khi gây lỗi |
| NFR-15 | Chi phí | Tổng chi phí LLM trong đồ án ≤ ngân sách đặt ra (chờ chốt) | Bảng theo dõi usage của nhà cung cấp |

## 9. Ma trận truy vết

Mọi user story trong PRD đều có use case, yêu cầu chức năng và tiêu chí nghiệm thu tương ứng; test case sau này sẽ thêm một cột vào bảng này.

| User story | Use case | Yêu cầu chức năng | Tiêu chí nghiệm thu (PRD) |
| --- | --- | --- | --- |
| US-01 | UC01, UC02 | FR-AUTH-01 đến 06 | AC-01, AC-05 |
| US-02 | UC03 | FR-CAT-04 | AC-01 |
| US-03 | UC04 | FR-SCH-01 đến 05 | AC-02 |
| US-04 | UC05 | FR-APT-01, FR-SCH-06 | AC-01, AC-03 |
| US-05 | UC06, UC07 | FR-APT-02, 03, 05, 06 | AC-04, AC-06 |
| US-06 | UC08 | FR-APT-04 | AC-01 |
| US-07 | UC09 | FR-AGT-01 đến 03, FR-SCH-04 | AC-10 |
| US-08 | UC09 | FR-AGT-05, FR-SCH-05 | AC-11 |
| US-09 | UC09, UC10 | FR-AGT-04 | AC-12, AC-13 |
| US-10 | UC09, UC11 | FR-AGT-06, 07 | AC-14 |
| US-11 | UC12 | FR-DOC-01 | AC-09 |
| US-12 | UC13, UC14 | FR-CAT-01 đến 03, 05; FR-ADM-01 | AC-07 |
| US-13 | UC15 | FR-ADM-02 | AC-07, AC-08 |
| US-14 | UC16 | FR-ADM-03, 04 | AC-08 |
| US-15 | UC17 | FR-NTF-01 đến 03 | AC-16 |
| US-16 | UC18 | FR-DOC-02, 03 | AC-17 |
| US-17 | UC19 | FR-RPT-01 | AC-18 |
| US-18 | UC20 | FR-RPT-02, 03 | AC-19 |

Các yêu cầu không gắn với một user story riêng (FR-AGT-08, 09 và toàn bộ NFR) được kiểm chứng qua AC-15 (đánh giá Agent) và AC-20 (bàn giao).
