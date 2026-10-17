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
