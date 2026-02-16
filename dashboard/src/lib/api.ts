const BASE = "/api/v1";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface FlagSummary {
  flag_name: string;
  variants: string[];
  total_assignments: number;
  success_rate: number | null;
}

export interface VariantMetrics {
  variant_name: string;
  assignments: number;
  success_count: number;
  failure_count: number;
  success_rate: number | null;
  avg_latency_ms: number | null;
  avg_cost: number | null;
  avg_input_tokens: number | null;
  avg_output_tokens: number | null;
  custom_events: Record<string, number>;
}

export interface FlagDetail {
  flag_name: string;
  total_assignments: number;
  variants: VariantMetrics[];
}

export interface TimelinePoint {
  date: string;
  variant_name: string;
  assignments: number;
  success_rate: number | null;
  avg_latency_ms: number | null;
  avg_cost: number | null;
}

export const api = {
  listFlags: () => fetchJSON<FlagSummary[]>("/flags"),
  getFlag: (name: string) => fetchJSON<FlagDetail>(`/flags/${name}`),
  getTimeline: (name: string) => fetchJSON<TimelinePoint[]>(`/flags/${name}/timeline`),
};
