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
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";

// Chart colors that adapt to theme
const getChartColor = (index: number) => {
  const colors = [
    "var(--color-chart-1)",
    "var(--color-chart-2)",
    "var(--color-chart-3)",
    "var(--color-chart-4)",
    "var(--color-chart-5)",
  ];
  return colors[index % colors.length];
};

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
        <Button variant="ghost" size="sm" asChild>
          <Link to="/">&larr; All experiments</Link>
        </Button>
      </div>

      <h1 className="text-2xl font-bold tracking-tight mb-1">{detail.flag_name}</h1>
      <p className="text-sm text-muted-foreground mb-8">
        {detail.total_assignments.toLocaleString()} total assignments across{" "}
        {detail.variants.length} variants
      </p>

      {/* Variant cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-10">
        {detail.variants.map((v, i) => (
          <Card key={v.variant_name} className="shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: getChartColor(i) }}
                />
                {v.variant_name}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-0">
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
                <>
                  <Separator className="my-3" />
                  <div className="space-y-2">
                    <h4 className="text-xs font-medium text-muted-foreground">Custom Events</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(v.custom_events).map(([name, count]) => (
                        <Badge key={name} variant="outline" className="text-xs">
                          {name}: {count}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
        {/* Success Rate Comparison */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Success Rate (%)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={comparisonData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="Success Rate" fill={getChartColor(0)} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Latency Comparison */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Avg Latency (ms)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={comparisonData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="Avg Latency (ms)" fill={getChartColor(1)} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Cost Comparison */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Avg Cost ($)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={comparisonData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="Avg Cost ($)" fill={getChartColor(2)} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Assignments Over Time */}
        {timelineData.length > 0 && (
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Assignments Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={timelineData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  {variants.map((v, i) => (
                    <Line
                      key={v}
                      type="monotone"
                      dataKey={v}
                      stroke={getChartColor(i)}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
