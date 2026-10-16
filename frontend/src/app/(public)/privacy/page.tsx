import type { Metadata } from "next";

import { CLINIC } from "@/shared/texts";
import { Card } from "@/shared/ui/card";

export const metadata: Metadata = { title: "Chính sách xử lý dữ liệu cá nhân" };

// Bản tóm tắt theo System Design mục 4.6, 7.7, 11.8. Bản đầy đủ cần người có chuyên môn pháp lý
// rà soát trước khi phục vụ bệnh nhân thật.
const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "Dữ liệu được thu thập",
    items: [
      "Họ tên, email, số điện thoại, ngày sinh, giới tính khi bạn đăng ký.",
      "Lịch hẹn, lý do khám và ghi chú của bác sĩ sau khám.",
      "Nội dung bạn trò chuyện với trợ lý đặt lịch.",
    ],
  },
  {
    title: "Mục đích sử dụng",
    items: [
      "Đặt, đổi, hủy lịch khám và nhận diện bạn khi đến phòng khám.",
      "Liên hệ khi lịch thay đổi; gửi email xác nhận và nhắc lịch.",
    ],
  },
  {
    title: "Ai xem được dữ liệu",
    items: [
      "Bạn xem toàn bộ thông tin và lịch hẹn của mình.",
      "Bác sĩ chỉ xem lịch hẹn mình khám: họ tên, tuổi, dịch vụ, giờ, lý do khám; không xem email, số điện thoại.",
      "Quản trị phòng khám xem để vận hành lịch hẹn.",
      "Trợ lý AI chỉ nhận phần thông tin cần để trả lời yêu cầu của bạn.",
    ],
  },
  {
    title: "Thời gian lưu và quyền của bạn",
    items: [
      "Nội dung trò chuyện với trợ lý được lưu tối đa 365 ngày rồi tự xóa.",
      "Bạn sửa được thông tin cá nhân (trừ email) trong mục Tài khoản.",
      "Bạn có thể yêu cầu xóa tài khoản: thông tin định danh được ẩn danh hóa, lịch sắp tới bị hủy.",
    ],
  },
];

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 md:px-6 md:py-12">
      <h1 className="text-[28px] leading-9 font-bold">Chính sách xử lý dữ liệu cá nhân</h1>
      <p className="mt-2 text-muted">
        {CLINIC.name} xử lý dữ liệu cá nhân của bạn theo Nghị định 13/2023/NĐ-CP. Lý do khám và ghi
        chú của bác sĩ là thông tin liên quan sức khỏe nên được bảo vệ ở mức cao nhất.
      </p>
      <div className="mt-6 flex flex-col gap-4">
        {SECTIONS.map((section) => (
          <Card key={section.title} className="p-5">
            <h2 className="text-lg font-semibold">{section.title}</h2>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-subtle">
              {section.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </main>
  );
}
