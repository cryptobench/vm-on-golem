import { cn } from "@golem/ui";
import type { HistoryRange } from "../lib/types";

const RANGES: HistoryRange[] = ["1h", "6h", "24h", "7d", "30d"];

export function RangePicker({
  value,
  onChange,
}: {
  value: HistoryRange;
  onChange: (range: HistoryRange) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-md border border-border bg-surface">
      {RANGES.map((range) => (
        <button
          key={range}
          type="button"
          className={cn(
            "h-8 min-w-10 px-3 text-sm transition",
            value === range
              ? "bg-primary text-white"
              : "text-text-secondary hover:bg-surface-muted hover:text-text-primary",
          )}
          onClick={() => onChange(range)}
        >
          {range}
        </button>
      ))}
    </div>
  );
}
