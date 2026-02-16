import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type FlagSummary } from "@/lib/api";
import { pct } from "@/lib/utils";

export default function Overview() {
  const [flags, setFlags] = useState<FlagSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listFlags().then(setFlags).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-muted-foreground animate-pulse">Loading flags...</div>;
  }

  if (flags.length === 0) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold mb-2">No experiments yet</h2>
        <p className="text-muted-foreground">
          Initialize the SDK and start assigning variants to see data here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Experiments</h1>
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="text-left px-4 py-3 font-medium">Flag</th>
              <th className="text-left px-4 py-3 font-medium">Variants</th>
              <th className="text-right px-4 py-3 font-medium">Assignments</th>
              <th className="text-right px-4 py-3 font-medium">Success Rate</th>
            </tr>
          </thead>
          <tbody>
            {flags.map((f) => (
              <tr key={f.flag_name} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3">
                  <Link to={`/flags/${f.flag_name}`} className="font-medium text-primary hover:underline">
                    {f.flag_name}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5 flex-wrap">
                    {f.variants.map((v) => (
                      <span key={v} className="inline-block rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                        {v}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{f.total_assignments.toLocaleString()}</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  <span className={f.success_rate != null && f.success_rate >= 0.9 ? "text-success font-medium" : ""}>
                    {pct(f.success_rate)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
