# PRD — Hệ thống đặt lịch khám bệnh tích hợp AI Agent

Oct 10, 2026 · @Viet · Phiên bản 0.1 (bản nháp)

## 1. Tổng quan và vấn đề

Sản phẩm giúp bệnh nhân của **một phòng khám** đặt, đổi, hủy lịch khám trực tuyến trong vài phút, bằng giao diện web hoặc bằng cách trò chuyện với AI Agent, thay vì gọi điện hay xếp hàng.

**Vấn đề cần giải quyết**

- **Bệnh nhân** không thấy được lịch trống, phải gọi điện hoặc đến trực tiếp, và khó tìm khung giờ khớp nhiều điều kiện cùng lúc (ngày, buổi, bác sĩ, dịch vụ).
- **Phòng khám** xếp lịch thủ công, dễ trùng giờ, mất nhiều công sức khi bác sĩ nghỉ hoặc bệnh nhân đổi lịch.
- **Hệ thống đặt lịch dạng form** bắt người dùng lọc qua nhiều bước; với yêu cầu như "sáng thứ Bảy tuần sau, khám da liễu, bác sĩ nào cũng được" thì thao tác chậm và dễ bỏ cuộc.

**Giải pháp đề xuất**: một website cho 3 vai trò (bệnh nhân, bác sĩ, quản trị), một Scheduling Engine bảo đảm không trùng lịch, và một AI Agent hiểu yêu cầu bằng ngôn ngữ tự nhiên. Agent dùng chung API nghiệp vụ với website và chỉ ghi dữ liệu sau khi bệnh nhân xác nhận.

**Bối cảnh**: đồ án chuyên ngành cá nhân, thời gian 8 tuần (từ 10/10/2026 đến khoảng đầu tháng 12/2026), repository `DACN_23020172`.

## 2. Mục tiêu và chỉ số thành công

Mục tiêu chính: bệnh nhân hoàn thành đặt lịch không cần nhân viên hỗ trợ, phòng khám không bao giờ có lịch trùng, và Agent giúp xử lý yêu cầu nhiều ràng buộc nhanh hơn thao tác thủ công.

| Mục tiêu | Chỉ số đo | Mức đạt (đề xuất) |
| --- | --- | --- |
| Đặt lịch tự phục vụ | Tỷ lệ hoàn thành tác vụ đặt lịch trên web trong phiên thử nghiệm | ≥ 90% |
| Không trùng lịch | Số lịch hẹn chồng thời gian của cùng bác sĩ sau test đặt đồng thời | 0 |
| Agent hiểu đúng yêu cầu | Tỷ lệ tác vụ trong bộ kịch bản kiểm thử Agent hoàn thành đúng | ≥ 80% |
| Agent an toàn | Số lần Agent ghi dữ liệu khi chưa có xác nhận | 0 |
| Hiệu quả của Agent | Thời gian và số thao tác so với web, với tác vụ nhiều ràng buộc | Agent ít thao tác hơn |
| Hiệu năng | Thời gian phản hồi API tìm lịch trống (p95, dữ liệu mẫu) | < 500 ms |

Các ngưỡng trên là đề xuất ban đầu, sẽ chốt lại sau khi có bộ dữ liệu và kịch bản đánh giá ở tuần 7.

## 3. Người dùng mục tiêu

Hệ thống có 3 vai trò đăng nhập; AI Agent không phải người dùng mà là một kênh thao tác thứ hai dành cho bệnh nhân.

| Vai trò | Persona đại diện | Nhu cầu chính | Nỗi đau hiện tại |
| --- | --- | --- | --- |
| Bệnh nhân | Chị Lan, 32 tuổi, nhân viên văn phòng, dùng điện thoại thành thạo, chỉ rảnh cuối tuần | Tìm nhanh lịch trống phù hợp, đặt/đổi/hủy không cần gọi điện | Không biết bác sĩ nào còn chỗ; đổi lịch phải gọi nhiều lần |
| Bệnh nhân lớn tuổi | Chú Hùng, 60 tuổi, ít quen thao tác nhiều bước | Nói yêu cầu bằng câu tự nhiên, được hướng dẫn từng bước | Form nhiều bộ lọc khó dùng |
| Bác sĩ | BS. Minh, khoa Nội, khám theo ca | Xem lịch khám trong ngày, cập nhật trạng thái và ghi chú ngắn | Lịch thay đổi không được báo kịp |
| Quản trị viên | Chị Hà, điều phối của phòng khám | Thiết lập khoa, bác sĩ, dịch vụ, ca làm, ngày nghỉ; theo dõi số liệu | Xếp lịch thủ công, dễ trùng |

Trong MVP, quản trị viên kiêm vai trò lễ tân (xử lý các trường hợp Agent chuyển sang nhân viên).

## 4. Phạm vi MVP

MVP gồm toàn bộ luồng đặt lịch trên web, Scheduling Engine và Agent đặt/đổi/hủy sau xác nhận; 4 tính năng phụ được giữ nhưng xếp ưu tiên để có thể cắt bớt nếu chậm tiến độ.

**Mức ưu tiên**

| Mức | Ý nghĩa | Tính năng |
| --- | --- | --- |
| P0 — Bắt buộc | Thiếu thì đồ án không đạt | Đăng ký/đăng nhập, phân quyền; quản lý khoa, bác sĩ, dịch vụ, ca làm, ngày nghỉ; tìm lịch trống; đặt/đổi/hủy lịch trên web; lịch sử khám của bệnh nhân; lịch khám của bác sĩ; chống trùng lịch; AI Agent tìm lịch, gợi ý thay thế, đặt/đổi/hủy sau xác nhận |
| P1 — Nên có | Làm trong tuần 4–6 nếu đúng tiến độ | Email xác nhận và nhắc lịch trước giờ khám; bác sĩ cập nhật trạng thái và ghi chú ngắn sau khám |
| P2 — Có thì tốt | Làm ở tuần 7 nếu còn thời gian, cắt đầu tiên khi trễ | Dashboard thống kê cho quản trị; bệnh nhân đánh giá bác sĩ sau khám |

**Ngoài phạm vi phiên bản này**

- Chẩn đoán bệnh, hoặc Agent suy luận chuyên khoa từ triệu chứng.
- Hồ sơ bệnh án điện tử đầy đủ, đơn thuốc, kết quả xét nghiệm.
- Thanh toán trực tuyến thật, bảo hiểm y tế.
- Nhiều phòng khám hoặc nhiều chi nhánh.
- Voicebot, ứng dụng di động native, thông báo SMS/Zalo.
- Dự đoán thời lượng khám bằng machine learning.
- Dữ liệu bệnh nhân thật: toàn bộ dữ liệu là dữ liệu giả lập.

## 5. Chức năng chính và user stories

Mỗi user story có mã để tham chiếu từ tiêu chí nghiệm thu và test case sau này.

| Mã | Vai trò | User story | Ưu tiên |
| --- | --- | --- | --- |
| US-01 | Bệnh nhân | Tôi đăng ký, đăng nhập bằng email và mật khẩu để quản lý lịch của mình | P0 |
| US-02 | Bệnh nhân | Tôi tìm bác sĩ theo chuyên khoa, dịch vụ hoặc tên để chọn nơi khám phù hợp | P0 |
| US-03 | Bệnh nhân | Tôi xem các khung giờ còn trống theo ngày để chọn giờ hợp với mình | P0 |
| US-04 | Bệnh nhân | Tôi đặt lịch và nhận mã lịch hẹn ngay sau khi xác nhận | P0 |
| US-05 | Bệnh nhân | Tôi đổi hoặc hủy lịch trước giờ khám theo quy định của phòng khám | P0 |
| US-06 | Bệnh nhân | Tôi xem danh sách lịch sắp tới và lịch sử đã khám | P0 |
| US-07 | Bệnh nhân | Tôi nói yêu cầu bằng câu tự nhiên với Agent để được gợi ý lịch phù hợp | P0 |
| US-08 | Bệnh nhân | Khi không còn lịch đúng yêu cầu, Agent gợi ý phương án gần nhất | P0 |
| US-09 | Bệnh nhân | Tôi nhờ Agent đặt, đổi hoặc hủy lịch và chỉ thực hiện khi tôi xác nhận | P0 |
| US-10 | Bệnh nhân | Tôi chưa biết khám dịch vụ nào thì Agent tìm theo mô tả và giải thích phạm vi khám của từng dịch vụ | P0 |
| US-11 | Bác sĩ | Tôi xem lịch khám theo ngày/tuần, kèm thông tin bệnh nhân và dịch vụ | P0 |
| US-12 | Quản trị | Tôi quản lý chuyên khoa, bác sĩ, dịch vụ và thời lượng khám của từng dịch vụ | P0 |
| US-13 | Quản trị | Tôi thiết lập ca làm việc lặp lại và ngày nghỉ của bác sĩ | P0 |
| US-14 | Quản trị | Tôi xem và xử lý mọi lịch hẹn, kể cả yêu cầu Agent chuyển sang nhân viên | P0 |
| US-15 | Bệnh nhân | Tôi nhận email xác nhận khi đặt/đổi/hủy và email nhắc trước giờ khám | P1 |
| US-16 | Bác sĩ | Tôi cập nhật trạng thái (đã đến, đã khám, vắng mặt) và ghi chú ngắn sau khám | P1 |
| US-17 | Quản trị | Tôi xem dashboard: số lịch theo ngày, tỷ lệ hủy, tải của từng bác sĩ | P2 |
| US-18 | Bệnh nhân | Tôi đánh giá bác sĩ (1–5 sao, nhận xét) sau khi lịch ở trạng thái đã khám | P2 |

## 6. AI Agent

Agent là một khung chat trên website dành cho bệnh nhân đã đăng nhập: nó đọc dữ liệu qua các công cụ (tool) gọi API backend, và mọi thao tác ghi chỉ chạy sau khi bệnh nhân bấm xác nhận.

**Công cụ của Agent**

| Công cụ | Việc làm | Loại |
| --- | --- | --- |
| `search_services` | Tìm dịch vụ, chuyên khoa theo từ khóa hoặc mô tả; trả về phạm vi khám của dịch vụ | Đọc |
| `search_doctors` | Tìm bác sĩ theo chuyên khoa, dịch vụ, tên | Đọc |
| `find_available_slots` | Tìm khung giờ trống theo dịch vụ, bác sĩ (tùy chọn), khoảng ngày, buổi trong ngày | Đọc |
| `get_my_appointments` | Liệt kê lịch hẹn của chính bệnh nhân đang đăng nhập | Đọc |
| `propose_booking` | Tạo đề xuất đặt/đổi/hủy lịch, hiển thị thẻ có nút Xác nhận và Hủy | Đề xuất |
| `handoff_to_staff` | Chuyển yêu cầu kèm tóm tắt hội thoại sang quản trị viên | Ghi (không đổi lịch) |

**Cơ chế xác nhận**: Agent không có công cụ trực tiếp tạo/đổi/hủy lịch. Nó chỉ tạo một đề xuất có thời hạn; backend thực hiện khi nhận yêu cầu xác nhận từ giao diện của bệnh nhân, rồi kiểm tra lại khung giờ còn trống trước khi ghi. Nhờ vậy, kể cả khi mô hình hiểu sai, dữ liệu không bị ghi nếu người dùng chưa đồng ý.

**Giới hạn hành vi**

- Không chẩn đoán, không suy luận chuyên khoa từ triệu chứng; khi người dùng mô tả triệu chứng, Agent nói rõ giới hạn này, gợi ý tìm theo dịch vụ hoặc chuyển nhân viên.
- Chỉ nêu khung giờ do công cụ trả về, không tự đưa ra giờ khám.
- Chỉ thấy và thao tác trên lịch hẹn của tài khoản đang đăng nhập.
- Giao tiếp bằng tiếng Việt; hiểu mốc thời gian tương đối ("thứ Bảy tuần sau", "chiều mai").
- Khi công cụ lỗi hoặc không có kết quả, Agent giải thích ngắn và đưa phương án thay thế (ngày gần nhất, bác sĩ khác, chuyển nhân viên).
- Câu hỏi ngoài phạm vi đặt lịch được từ chối lịch sự.

## 7. Quy tắc nghiệp vụ

Các quy tắc này áp dụng ở backend cho cả web và Agent; chúng quyết định thiết kế database, API và test.

| Mã | Quy tắc |
| --- | --- |
| BR-01 | Một bác sĩ không có hai lịch hẹn chồng thời gian; ràng buộc được bảo đảm ở tầng database, không chỉ ở code. |
| BR-02 | Thời lượng khám do dịch vụ quy định (ví dụ 15, 30, 45 phút); khung giờ trống được tính từ ca làm, ngày nghỉ, lịch đã đặt và thời lượng dịch vụ. |
| BR-03 | Hai bệnh nhân cùng đặt một khung giờ thì chỉ một người thành công; người còn lại nhận thông báo và gợi ý khung khác. |
| BR-04 | Đổi lịch là một giao dịch: nếu tạo lịch mới thất bại thì lịch cũ giữ nguyên. |
| BR-05 | Bệnh nhân chỉ xem, đổi, hủy lịch của chính mình; bác sĩ chỉ xem lịch của mình; quản trị thao tác được mọi lịch. |
| BR-06 | Agent chỉ ghi dữ liệu khi có xác nhận hợp lệ từ bệnh nhân; đề xuất hết hạn sau một khoảng thời gian (đề xuất 10 phút). |
| BR-07 | Chỉ đặt lịch trong tương lai, trong cửa sổ đặt trước tối đa (đề xuất 30 ngày). |
| BR-08 | Bệnh nhân chỉ đổi/hủy trước giờ khám một khoảng tối thiểu (đề xuất 2 giờ); sau mốc đó phải liên hệ phòng khám. |
| BR-09 | Một bệnh nhân không có hai lịch hẹn trùng giờ với nhau (đề xuất giới hạn tối đa 3 lịch đang chờ). |
| BR-10 | Khi quản trị thêm ngày nghỉ trùng lịch đã đặt, hệ thống liệt kê các lịch bị ảnh hưởng để quản trị xử lý; không tự xóa. |
| BR-11 | Trạng thái lịch hẹn: Đã đặt → Đã đến → Đã khám, hoặc Đã đặt → Đã hủy / Vắng mặt. Chỉ lịch Đã khám mới được đánh giá. |

Các con số đánh dấu "đề xuất" là giá trị cấu hình, có thể đổi mà không sửa code.

## 8. Yêu cầu phi chức năng

| Nhóm | Yêu cầu |
| --- | --- |
| Bảo mật | Mật khẩu băm (bcrypt/argon2); xác thực JWT hoặc session; phân quyền kiểm tra ở mọi API; không commit secret, API key hay file `.env`. |
| Toàn vẹn dữ liệu | Đặt/đổi/hủy chạy trong transaction; ràng buộc chống chồng lịch ở PostgreSQL. |
| Hiệu năng | API tìm lịch trống p95 < 500 ms với dữ liệu mẫu (khoảng 20 bác sĩ, 30 ngày lịch); Agent trả lời trong khoảng 10 giây mỗi lượt. |
| Khả dụng | Giao diện chạy tốt trên trình duyệt desktop và điện thoại (responsive), tiếng Việt. |
| Quan sát | Ghi log mỗi lần Agent gọi công cụ (đầu vào, kết quả, thời gian) để phục vụ đánh giá và gỡ lỗi. |
| Kiểm thử | Unit test cho Scheduling Engine và quy tắc nghiệp vụ; test đặt lịch đồng thời; E2E cho luồng đặt lịch chính; bộ kịch bản đánh giá Agent. |
| Triển khai | Chạy toàn bộ bằng một lệnh Docker Compose; có bản demo truy cập được khi bảo vệ. |
| Dữ liệu | Chỉ dùng dữ liệu giả lập; có script tạo dữ liệu mẫu (seed). |
| Chi phí | Chi phí gọi LLM trong toàn đồ án nằm trong ngân sách cá nhân; có giới hạn số lượt chat mỗi người dùng. |

## 9. Tiêu chí nghiệm thu

Đồ án được coi là hoàn thành khi toàn bộ tiêu chí P0 đạt; P1, P2 tính là điểm cộng. Mỗi tiêu chí sẽ có ít nhất một test tương ứng.

**Đặt lịch trên web (P0)**

- [ ] AC-01: Bệnh nhân mới đăng ký, đăng nhập, chọn dịch vụ → bác sĩ → khung giờ → xác nhận, và thấy lịch trong danh sách "Sắp tới" (US-01 đến US-06).
- [ ] AC-02: Khung giờ hiển thị không bao gồm giờ ngoài ca, ngày nghỉ, giờ đã có người đặt, và khớp thời lượng dịch vụ (BR-02).
- [ ] AC-03: 20 yêu cầu đặt đồng thời vào cùng một khung giờ chỉ tạo đúng 1 lịch hẹn; 19 yêu cầu còn lại nhận lỗi rõ ràng (BR-01, BR-03).
- [ ] AC-04: Đổi lịch sang khung giờ vừa bị người khác đặt thì thất bại và lịch cũ vẫn còn nguyên (BR-04).
- [ ] AC-05: Bệnh nhân A gọi API xem/đổi/hủy lịch của bệnh nhân B thì nhận lỗi 403 (BR-05).
- [ ] AC-06: Hủy hoặc đổi lịch sau mốc tối thiểu trước giờ khám bị từ chối kèm hướng dẫn (BR-08).

**Bác sĩ và quản trị (P0)**

- [ ] AC-07: Quản trị tạo chuyên khoa, dịch vụ (có thời lượng), bác sĩ, ca làm lặp lại; khung giờ trống mới xuất hiện ngay cho bệnh nhân.
- [ ] AC-08: Quản trị thêm ngày nghỉ trùng lịch đã đặt thì thấy danh sách lịch bị ảnh hưởng (BR-10).
- [ ] AC-09: Bác sĩ đăng nhập chỉ thấy lịch khám của chính mình, xem theo ngày và tuần.

**AI Agent (P0)**

- [ ] AC-10: Với câu "Tôi muốn khám da liễu sáng thứ Bảy tuần sau", Agent trả về các khung giờ có thật trong hệ thống, đúng ngày và đúng buổi.
- [ ] AC-11: Khi không còn khung đúng yêu cầu, Agent đưa ít nhất một phương án thay thế gần nhất.
- [ ] AC-12: Agent đặt, đổi, hủy lịch thành công qua thẻ xác nhận; kết quả trên web giống hệt như khi thao tác bằng giao diện.
- [ ] AC-13: Nếu bệnh nhân không bấm xác nhận, hoặc đề xuất đã hết hạn, không có dữ liệu nào bị ghi (BR-06).
- [ ] AC-14: Khi người dùng mô tả triệu chứng, Agent không chẩn đoán, nêu giới hạn và gợi ý tìm dịch vụ hoặc chuyển nhân viên.
- [ ] AC-15: Trên bộ kịch bản kiểm thử Agent (đề xuất 30–50 kịch bản), tỷ lệ hoàn thành đúng ≥ 80% và 0 lần ghi dữ liệu sai quyền hoặc chưa xác nhận.

**Tính năng phụ (P1, P2)**

- [ ] AC-16 (P1): Email xác nhận được gửi sau khi đặt/đổi/hủy; email nhắc gửi trước giờ khám (đề xuất 24 giờ).
- [ ] AC-17 (P1): Bác sĩ đổi trạng thái lịch và lưu ghi chú; bệnh nhân thấy trạng thái mới.
- [ ] AC-18 (P2): Dashboard hiển thị số lịch theo ngày, tỷ lệ hủy, số lịch của từng bác sĩ, khớp với dữ liệu trong database.
- [ ] AC-19 (P2): Chỉ lịch ở trạng thái Đã khám mới đánh giá được, mỗi lịch một lần.

**Bàn giao**

- [ ] AC-20: `docker compose up` dựng được toàn bộ hệ thống kèm dữ liệu mẫu; README hướng dẫn chạy; có báo cáo đánh giá so sánh web và Agent (tỷ lệ hoàn thành, thời gian, số thao tác, lỗi).

## 10. Giả định, rủi ro và câu hỏi mở

**Giả định**

- Một phòng khám, một múi giờ (Asia/Ho\_Chi\_Minh), giao diện và Agent bằng tiếng Việt.
- Mỗi lịch hẹn gắn với một bác sĩ và một dịch vụ; không có phòng khám/thiết bị là tài nguyên riêng.
- Bệnh nhân tự đặt cho chính mình; chưa hỗ trợ đặt hộ người thân.
- Stack theo kế hoạch: React + TypeScript, FastAPI, PostgreSQL, LangGraph hoặc OpenAI Agents SDK, Docker Compose.

**Rủi ro**

| Rủi ro | Ảnh hưởng | Cách giảm |
| --- | --- | --- |
| Ôm cả 4 tính năng phụ làm trễ phần lõi | Không đạt cột mốc tuần 4 | Giữ thứ tự P0 → P1 → P2; cắt P2 đầu tiên |
| Agent hiểu sai ngày giờ tương đối | Đề xuất sai lịch | Công cụ nhận ngày dạng chuẩn, Agent nhắc lại ngày cụ thể trên thẻ xác nhận |
| Lỗi đặt trùng khi đồng thời | Vi phạm BR-01 | Ràng buộc ở database + test đồng thời từ tuần 3 |
| Chi phí hoặc giới hạn API của LLM | Không demo được | Giới hạn lượt chat, chọn mô hình rẻ cho phát triển, cache kịch bản test |
| Giảng viên yêu cầu đổi phạm vi | Phải sửa thiết kế | Gửi PRD xin ý kiến trong tuần 1 trước khi viết code |
