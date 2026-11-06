// Tên ngắn cho các kiểu sinh từ OpenAPI (schema.d.ts), để component không lặp components["schemas"].
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Specialty = Schemas["SpecialtyOut"];
export type Service = Schemas["ServiceOut"];
export type ServiceBrief = Schemas["ServiceBrief"];
export type Doctor = Schemas["DoctorOut"];
export type DoctorDetail = Schemas["DoctorDetail"];
export type DoctorRef = Schemas["DoctorRef"];
export type WorkingHours = Schemas["WorkingHours"];
export type Availability = Schemas["AvailabilityOut"];
export type AvailabilityDay = Schemas["DayOut"];
export type AvailabilitySlot = Schemas["SlotOut"];
export type EarliestItem = Schemas["EarliestItem"];
export type Gender = Doctor["gender"];
export type Appointment = Schemas["AppointmentOut"];
export type AppointmentDetail = Schemas["AppointmentDetail"];
export type AppointmentPage = Schemas["AppointmentPage"];
export type AppointmentStatus = Schemas["AppointmentStatus"];
export type AppointmentScope = Schemas["Scope"];
export type HistoryEntry = Schemas["HistoryEntry"];
export type Channel = Schemas["Channel"];
export type Me = Schemas["MeResponse"];
export type PatientBrief = Schemas["PatientBrief"];
export type PastVisit = Schemas["PastVisit"];
// Bác sĩ (D-day, D-week, D-detail)
export type DoctorSchedule = Schemas["DoctorScheduleOut"];
export type ScheduleAppointment = Schemas["ScheduleAppointment"];
export type TimeBlock = Schemas["TimeBlock"];
export type TimeOffBlock = Schemas["TimeOffBlock"];
// Quản trị (AD-*)
export type AdminAppointment = Schemas["AdminAppointmentOut"];
export type AdminAppointmentPage = Schemas["AdminAppointmentPage"];
export type AttentionSource = Schemas["AttentionSource"];
export type SupportRequest = Schemas["SupportRequestAdminOut"];
export type SpecialtyAdmin = Schemas["SpecialtyAdminOut"];
export type ServiceAdmin = Schemas["ServiceAdminOut"];
export type DoctorAdmin = Schemas["DoctorAdminOut"];
export type Shift = Schemas["ShiftOut"];
export type TimeOff = Schemas["TimeOffOut"];
export type AffectedAppointment = Schemas["AffectedOut"];
