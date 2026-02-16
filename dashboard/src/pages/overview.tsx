import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type FlagSummary } from "@/lib/api";
import { pct } from "@/lib/utils";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function Overview() {
  const [flags, setFlags] = useState<FlagSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listFlags().then(setFlags).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
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
      <h1 className="text-2xl font-bold tracking-tight mb-6">Experiments</h1>
      <div className="rounded-xl border border-border overflow-hidden shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="font-semibold">Flag</TableHead>
              <TableHead className="font-semibold">Variants</TableHead>
              <TableHead className="text-right font-semibold">Assignments</TableHead>
              <TableHead className="text-right font-semibold">Success Rate</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {flags.map((f) => (
              <TableRow key={f.flag_name} className="hover:bg-muted/50 transition-colors">
                <TableCell>
                  <Link to={`/flags/${f.flag_name}`} className="font-medium text-primary hover:underline">
                    {f.flag_name}
                  </Link>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1.5 flex-wrap">
                    {f.variants.map((v) => (
                      <Badge key={v} variant="secondary">
                        {v}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">{f.total_assignments.toLocaleString()}</TableCell>
                <TableCell className="text-right tabular-nums">
                  <span className={f.success_rate != null && f.success_rate >= 0.9 ? "text-success font-medium" : ""}>
                    {pct(f.success_rate)}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
