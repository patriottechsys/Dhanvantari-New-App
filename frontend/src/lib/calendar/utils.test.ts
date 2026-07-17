import { describe, it, expect } from "vitest";
import {
  buildWeekDays, buildTimeSlots, positionForRange, layoutDay,
  snapToSlot, slotId, parseSlotId, draggableId, parseDraggableId,
  resolveDragEnd, SLOT_PX,
} from "./utils";
import type { Appointment } from "./types";

function appt(id: number, start: string, end: string): Appointment {
  return {
    id, patient_id: 1, practitioner_id: 1, start_at: start, end_at: end,
    appointment_type: "consultation", status: "scheduled",
    created_at: start, updated_at: start,
  };
}

describe("buildWeekDays", () => {
  it("returns 7 days starting Monday", () => {
    const days = buildWeekDays(new Date("2026-07-16T12:00:00")); // Thursday
    expect(days).toHaveLength(7);
    expect(days[0].getDay()).toBe(1); // Monday
    expect(days[0].getDate()).toBe(13);
    expect(days[6].getDate()).toBe(19);
  });
});

describe("buildTimeSlots", () => {
  it("spans 06:00 to 19:30 in 30-min steps", () => {
    const slots = buildTimeSlots();
    expect(slots[0].minutes).toBe(360);
    expect(slots[slots.length - 1].minutes).toBe(1170);
    expect(slots).toHaveLength(28);
  });
});

describe("positionForRange", () => {
  it("puts a 07:00-07:30 block two slots below the top", () => {
    const pos = positionForRange(new Date("2026-07-16T07:00:00"), new Date("2026-07-16T07:30:00"));
    expect(pos.top).toBe(2 * SLOT_PX);   // 06:00->07:00 == 2 slots
    expect(pos.height).toBe(SLOT_PX);    // 30 min == 1 slot
  });
});

describe("layoutDay", () => {
  it("splits two overlapping appointments into two columns", () => {
    const a = appt(1, "2026-07-16T09:00:00", "2026-07-16T10:00:00");
    const b = appt(2, "2026-07-16T09:30:00", "2026-07-16T10:30:00");
    const laid = layoutDay([a, b]);
    expect(laid).toHaveLength(2);
    expect(laid.every((x) => x.columns === 2)).toBe(true);
    expect(new Set(laid.map((x) => x.column))).toEqual(new Set([0, 1]));
  });

  it("keeps non-overlapping appointments in a single column", () => {
    const a = appt(1, "2026-07-16T09:00:00", "2026-07-16T09:30:00");
    const b = appt(2, "2026-07-16T10:00:00", "2026-07-16T10:30:00");
    const laid = layoutDay([a, b]);
    expect(laid.every((x) => x.columns === 1 && x.column === 0)).toBe(true);
  });
});

describe("slot id round-trip", () => {
  it("parses what it serializes", () => {
    const d = new Date("2026-07-16T09:30:00");
    const parsed = parseSlotId(slotId(d));
    expect(parsed?.getTime()).toBe(d.getTime());
  });
  it("returns null for non-slot ids", () => {
    expect(parseSlotId("patient:5")).toBeNull();
  });
});

describe("draggable id round-trip", () => {
  it("parses patient and appt ids", () => {
    expect(parseDraggableId(draggableId("patient", 5))).toEqual({ kind: "patient", id: 5 });
    expect(parseDraggableId(draggableId("appt", 9))).toEqual({ kind: "appt", id: 9 });
  });
});

describe("snapToSlot", () => {
  it("snaps 09:47 down to 09:30", () => {
    const snapped = snapToSlot(new Date("2026-07-16T09:47:00"));
    expect(snapped.getMinutes()).toBe(30);
    expect(snapped.getHours()).toBe(9);
  });
});

describe("resolveDragEnd", () => {
  const target = "2026-07-16T11:00:00";
  it("resolves patient -> slot as a booking", () => {
    const res = resolveDragEnd(draggableId("patient", 3), slotId(new Date(target)), []);
    expect(res).toEqual({ kind: "book", patientId: 3, start: new Date(target) });
  });
  it("resolves appt -> slot as a reschedule preserving duration", () => {
    const a = appt(7, "2026-07-16T09:00:00", "2026-07-16T10:00:00"); // 60 min
    const res = resolveDragEnd(draggableId("appt", 7), slotId(new Date(target)), [a]);
    expect(res).toEqual({
      kind: "reschedule", appointmentId: 7,
      start: new Date(target), end: new Date("2026-07-16T12:00:00"),
    });
  });
  it("returns null when dropped outside any slot", () => {
    expect(resolveDragEnd(draggableId("appt", 7), null, [])).toBeNull();
  });
});
