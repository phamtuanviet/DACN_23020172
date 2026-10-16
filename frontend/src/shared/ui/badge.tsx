// Nhãn trạng thái lịch hẹn: màu luôn đi kèm chữ, không chỉ dựa vào màu (hướng A).
import { cn } from "@/shared/lib/cn";

export type AppointmentStatus = "BOOKED" | "ARRIVED" | "COMPLETED" | "CANCELLED" | "NO_SHOW";

const STATUS: Record<AppointmentStatus, { label: string; className: string }> = {
  BOOKED: { label: "Đã đặt", className: "bg-booked-soft text-booked" },
  ARRIVED: { label: "Đã đến", className: "bg-arrived-soft text-arrived" },
  COMPLETED: { label: "Đã khám", className: "bg-completed-soft text-completed" },
  CANCELLED: { label: "Đã hủy", className: "bg-cancelled-soft text-cancelled" },
  NO_SHOW: { label: "Vắng mặt", className: "bg-noshow-soft text-noshow" },
};

export function StatusBadge({
  status,
  className,
}: {
  status: AppointmentStatus;
  className?: string;
}) {
  const { label, className: tone } = STATUS[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 text-xs leading-6 font-semibold",
        tone,
        className,
      )}
    >
      {label}
    </span>
  );
}

export function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-primary-soft px-3 py-1 text-sm font-semibold text-primary-ink",
        className,
      )}
    >
      {children}
    </span>
  );
}
