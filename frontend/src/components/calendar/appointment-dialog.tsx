"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { therapiesApi, plansApi } from "@/lib/api/client";
import type { Appointment, AppointmentType, AppointmentStatus, Patient, NewAppointmentDraft } from "@/lib/calendar/types";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const TYPES: AppointmentType[] = ["consultation", "follow_up", "therapy", "panchakarma"];
const STATUSES: AppointmentStatus[] = ["scheduled", "confirmed", "completed", "cancelled", "no_show"];

function toDateInput(d: Date) { return d.toLocaleDateString("en-CA"); }              // yyyy-mm-dd (local)
function toTimeInput(d: Date) { return d.toTimeString().slice(0, 5); }               // HH:MM (local)
function combine(dateStr: string, timeStr: string): Date { return new Date(`${dateStr}T${timeStr}`); }

export interface AppointmentSubmit {
  patient_id: number;
  start_at: string;
  end_at: string;
  appointment_type: AppointmentType;
  status?: AppointmentStatus;
  reason?: string;
  location?: string;
  notes?: string;
  therapy_id?: number | null;
  plan_id?: number | null;
}

export function AppointmentDialog({
  open, onClose, patients, draft, editing, onSubmit, isPending, error,
}: {
  open: boolean;
  onClose: () => void;
  patients: Patient[];
  draft: NewAppointmentDraft | null;
  editing: Appointment | null;
  onSubmit: (payload: AppointmentSubmit) => void;
  isPending: boolean;
  error: string | null;
}) {
  const initialStart = editing ? new Date(editing.start_at) : draft?.start ?? new Date();
  const initialEnd = editing ? new Date(editing.end_at) : draft?.end ?? new Date();

  const [patientId, setPatientId] = useState("");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [type, setType] = useState<AppointmentType>("consultation");
  const [status, setStatus] = useState<AppointmentStatus>("scheduled");
  const [reason, setReason] = useState("");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [therapyId, setTherapyId] = useState("");
  const [attachPlan, setAttachPlan] = useState(false);

  // Reset fields whenever the dialog opens for a new draft/edit.
  useEffect(() => {
    if (!open) return;
    setPatientId(editing ? String(editing.patient_id) : draft?.patientId ? String(draft.patientId) : "");
    setDate(toDateInput(initialStart));
    setStartTime(toTimeInput(initialStart));
    setEndTime(toTimeInput(initialEnd));
    setType(editing?.appointment_type ?? "consultation");
    setStatus(editing?.status ?? "scheduled");
    setReason(editing?.reason ?? "");
    setLocation(editing?.location ?? "");
    setNotes(editing?.notes ?? "");
    setTherapyId(editing?.therapy_id ? String(editing.therapy_id) : "");
    setAttachPlan(Boolean(editing?.plan_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing, draft]);

  const { data: therapies = [] } = useQuery<{ id: number; name: string }[]>({
    queryKey: ["therapies"],
    queryFn: () => therapiesApi.list().then((r) => r.data),
    enabled: open,
  });

  const { data: activePlan } = useQuery<{ id: number } | null>({
    queryKey: ["active-plan", patientId],
    queryFn: () => plansApi.get(Number(patientId)).then((r) => r.data).catch(() => null),
    enabled: open && !!patientId,
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      patient_id: Number(patientId),
      start_at: combine(date, startTime).toISOString(),
      end_at: combine(date, endTime).toISOString(),
      appointment_type: type,
      status: editing ? status : undefined,
      reason: reason || undefined,
      location: location || undefined,
      notes: notes || undefined,
      therapy_id: therapyId ? Number(therapyId) : null,
      plan_id: attachPlan && activePlan?.id ? activePlan.id : null,
    });
  }

  return (
    <Dialog open={open} onClose={onClose} title={editing ? "Edit appointment" : "New appointment"}>
      <form onSubmit={submit} className="space-y-4">
        {error && <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>}

        <div className="space-y-1.5">
          <Label>Patient *</Label>
          <Select required value={patientId} onChange={(e) => setPatientId(e.target.value)}>
            <option value="">Select patient…</option>
            {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </Select>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5 col-span-1">
            <Label>Date *</Label>
            <Input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Start *</Label>
            <Input type="time" required step={1800} value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>End *</Label>
            <Input type="time" required step={1800} value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label>Type</Label>
            <Select value={type} onChange={(e) => setType(e.target.value as AppointmentType)}>
              {TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
            </Select>
          </div>
          {editing && (
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={status} onChange={(e) => setStatus(e.target.value as AppointmentStatus)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </Select>
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <Label>Reason</Label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Panchakarma consult" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label>Location</Label>
            <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Clinic / Telehealth" />
          </div>
          <div className="space-y-1.5">
            <Label>Link therapy</Label>
            <Select value={therapyId} onChange={(e) => setTherapyId(e.target.value)}>
              <option value="">None</option>
              {therapies.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </div>
        </div>

        {activePlan?.id && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={attachPlan} onChange={(e) => setAttachPlan(e.target.checked)} />
            Attach to patient&apos;s active care plan
          </label>
        )}

        <div className="space-y-1.5">
          <Label>Notes</Label>
          <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={isPending}>{isPending ? "Saving…" : editing ? "Save" : "Book"}</Button>
        </div>
      </form>
    </Dialog>
  );
}
