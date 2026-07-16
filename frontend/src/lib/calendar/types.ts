export type AppointmentType = "consultation" | "follow_up" | "therapy" | "panchakarma";
export type AppointmentStatus = "scheduled" | "confirmed" | "completed" | "cancelled" | "no_show";

export interface Appointment {
  id: number;
  patient_id: number;
  practitioner_id: number;
  patient_name?: string | null;
  start_at: string;   // ISO
  end_at: string;     // ISO
  appointment_type: AppointmentType;
  status: AppointmentStatus;
  reason?: string | null;
  notes?: string | null;
  location?: string | null;
  plan_id?: number | null;
  therapy_id?: number | null;
  reminder_sent_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Patient {
  id: number;
  full_name: string;
}

export type DragResolution =
  | { kind: "book"; patientId: number; start: Date }
  | { kind: "reschedule"; appointmentId: number; start: Date; end: Date };

export interface NewAppointmentDraft {
  patientId?: number;
  start: Date;
  end: Date;
}
