import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { api, type FlagDetail, type TimelinePoint } from "@/lib/api";
import { fmt, pct } from "@/lib/utils";

const COLORS = ["#6366f1", "#f59e0b", "#10b981", "#f43f5e", "#8b5cf6"];

export default function FlagPage() {
  const { name } = useParams<{ name: string }>();
  const [detail, setDetail] = useState<FlagDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!name) return;
    Promise.all([api.getFlag(name), api.getTimeline(name)])
      .then(([d, t]) => {
        setDetail(d);
        setTimeline(t);
      })
      .finally(() => setLoading(false));
  }, [name]);

  if (loading || !detail) {
    return <div className="text-muted-foreground animate-pulse">Loading...</div>;
  }

  // Prepare chart data
  const comparisonData = detail.variants.map((v) => ({
    name: v.variant_name,
    "Success Rate": v.success_rate != null ? +(v.success_rate * 100).toFixed(1) : 0,
    "Avg Latency (ms)": v.avg_latency_ms != null ? +v.avg_latency_ms.toFixed(1) : 0,
    "Avg Cost ($)": v.avg_cost != null ? +v.avg_cost.toFixed(4) : 0,
  }));

  // Group timeline by date for line chart
  const variants = detail.variants.map((v) => v.variant_name);
  const dateMap = new Map<string, Record<string, number | null>>();
  for (const tp of timeline) {
    if (!dateMap.has(tp.date)) dateMap.set(tp.date, {});
    const entry = dateMap.get(tp.date)!;
    entry[tp.variant_name] = tp.assignments;
  }
  const timelineData = Array.from(dateMap.entries()).map(([date, vals]) => ({
    date,
    ...vals,
  }));

  return (
    <div>
      <div className="mb-6">
        <Link to="/" className="text-sm text-muted-foreground hover:text-primary transition-colors">
          &larr; All experiments
        </Link>
      </div>

      <h1 className="text-2xl font-bold mb-1">{detail.flag_name}</h1>
      <p className="text-muted-foreground mb-8">
        {detail.total_assignments.toLocaleString()} total assignments across{" "}
        {detail.variants.length} variants
      </p>

      {/* Variant cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
        {detail.variants.map((v, i) => (
          <div
            key={v.variant_name}
            className="rounded-xl border border-border bg-card p-5"
            style={{ borderTopColor: COLORS[i % COLORS.length], borderTopWidth: 3 }}
          >
            <h3 className="font-semibold text-base mb-3">{v.variant_name}</h3>
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Assignments</dt>
              <dd className="text-right tabular-nums font-medium">{v.assignments.toLocaleString()}</dd>

              <dt className="text-muted-foreground">Success Rate</dt>
              <dd className="text-right tabular-nums font-medium">{pct(v.success_rate)}</dd>

              <dt className="text-muted-foreground">Avg Latency</dt>
              <dd className="text-right tabular-nums">{fmt(v.avg_latency_ms)} ms</dd>

              <dt className="text-muted-foreground">Avg Cost</dt>
              <dd className="text-right tabular-nums">${fmt(v.avg_cost, 4)}</dd>

              <dt className="text-muted-foreground">Avg Input Tokens</dt>
              <dd className="text-right tabular-nums">{fmt(v.avg_input_tokens, 0)}</dd>

              <dt className="text-muted-foreground">Avg Output Tokens</dt>
              <dd className="text-right tabular-nums">{fmt(v.avg_output_tokens, 0)}</dd>
            </dl>

            {Object.keys(v.custom_events).length > 0 && (
              <div className="mt-3 pt-3 border-t border-border">
                <h4 className="text-xs font-medium text-muted-foreground mb-1">Custom Events</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(v.custom_events).map(([name, count]) => (
                    <span key={name} className="text-xs bg-muted rounded-full px-2 py-0.5">
                      {name}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
        {/* Success Rate Comparison */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="font-semibold mb-4">Success Rate (%)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="Success Rate" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Latency Comparison */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="font-semibold mb-4">Avg Latency (ms)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="Avg Latency (ms)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Cost Comparison */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="font-semibold mb-4">Avg Cost ($)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="Avg Cost ($)" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Assignments Over Time */}
        {timelineData.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="font-semibold mb-4">Assignments Over Time</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={timelineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                {variants.map((v, i) => (
                  <Line
                    key={v}
                    type="monotone"
                    dataKey={v}
                    stroke={COLORS[i % COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
