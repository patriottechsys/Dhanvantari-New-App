import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi } from "vitest";
import CalendarPage from "./page";

vi.mock("@/lib/api/client", () => ({
  appointmentsApi: { list: () => Promise.resolve({ data: [] }) },
  patientsApi: { list: () => Promise.resolve({ data: [] }) },
  therapiesApi: { list: () => Promise.resolve({ data: [] }) },
  plansApi: { get: () => Promise.resolve({ data: null }) },
}));

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("CalendarPage", () => {
  it("renders the header and patient panel", async () => {
    wrap(<CalendarPage />);
    expect(await screen.findByText("Appointments")).toBeInTheDocument();
    expect(screen.getByText("New appointment")).toBeInTheDocument();
    expect(screen.getByText("Patients")).toBeInTheDocument();
  });
});
