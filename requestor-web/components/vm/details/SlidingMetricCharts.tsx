"use client";

import React from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";
import { cn } from "../../ui/cn";
import {
  getAppendOnlySlideChange,
  type MetricChartRow,
  type MetricSparklineRow,
} from "./metrics";

type SeriesKey = Exclude<keyof MetricChartRow, "timestamp" | "time">;

type SeriesConfig = {
  key: SeriesKey;
  label: string;
  colorClassName: string;
  dotClassName: string;
};

const metricSeries: SeriesConfig[] = [
  {
    key: "CPU",
    label: "CPU",
    colorClassName: "text-blue-500",
    dotClassName: "bg-blue-500",
  },
  {
    key: "Memory",
    label: "Memory",
    colorClassName: "text-violet-500",
    dotClassName: "bg-violet-500",
  },
  {
    key: "Disk",
    label: "Disk",
    colorClassName: "text-emerald-500",
    dotClassName: "bg-emerald-500",
  },
  {
    key: "Network RX",
    label: "Network RX",
    colorClassName: "text-cyan-500",
    dotClassName: "bg-cyan-500",
  },
  {
    key: "Network TX",
    label: "Network TX",
    colorClassName: "text-orange-500",
    dotClassName: "bg-orange-500",
  },
];

const sparklineColors = {
  blue: "text-blue-500",
  violet: "text-violet-500",
  emerald: "text-emerald-500",
  cyan: "text-cyan-500",
  orange: "text-orange-500",
} as const;

type SlidingMetricLineChartProps = {
  className?: string;
  data: MetricChartRow[];
  categories: SeriesKey[];
  valueFormatter: (value: number) => string;
  minValue?: number;
  yAxisWidth?: number;
};

export function SlidingMetricLineChart({
  className,
  data,
  categories,
  valueFormatter,
  minValue,
  yAxisWidth = 56,
}: SlidingMetricLineChartProps) {
  const slide = useAppendSlide(
    data.map((row) => row.timestamp),
    yAxisWidth + 40,
  );
  const activeSeries = metricSeries.filter((series) =>
    categories.includes(series.key),
  );

  return (
    <div
      ref={slide.ref}
      className={cn("vm-sliding-chart flex min-h-0 flex-col", className)}
      data-slide-active={slide.active ? "true" : "false"}
      data-draw-active={slide.drawActive ? "true" : "false"}
      style={
        {
          "--vm-chart-slide-x": `${slide.offset}px`,
        } as React.CSSProperties
      }
    >
      <ChartLegend series={activeSeries} />
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 8, right: 20, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              vertical={false}
              className="stroke-border"
              stroke="currentColor"
            />
            <XAxis
              dataKey="time"
              tickLine={false}
              axisLine={false}
              minTickGap={18}
              padding={{ left: 20, right: 20 }}
              className="fill-text-primary text-xs"
            />
            <YAxis
              width={yAxisWidth}
              tickLine={false}
              axisLine={false}
              domain={[minValue ?? "auto", "auto"]}
              tickFormatter={valueFormatter}
              allowDecimals
              className="fill-text-primary text-xs"
            />
            <Tooltip
              isAnimationActive={false}
              cursor={{ stroke: "var(--border-strong)", strokeWidth: 1 }}
              content={
                <MetricTooltip
                  series={activeSeries}
                  valueFormatter={valueFormatter}
                />
              }
            />
            <Legend wrapperStyle={{ display: "none" }} />
            {activeSeries.map((series) => (
              <Line
                key={series.key}
                className={series.colorClassName}
                type="linear"
                dataKey={series.key}
                name={series.label}
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={false}
                activeDot={{ r: 4 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function SlidingSparkline({
  className,
  data,
  color,
}: {
  className?: string;
  data: MetricSparklineRow[];
  color: keyof typeof sparklineColors;
}) {
  const slide = useAppendSlide(
    data.map((row) => row.timestamp),
    2,
  );

  return (
    <div
      ref={slide.ref}
      className={cn("vm-sliding-chart", className)}
      data-slide-active={slide.active ? "true" : "false"}
      data-draw-active={slide.drawActive ? "true" : "false"}
      style={
        {
          "--vm-chart-slide-x": `${slide.offset}px`,
        } as React.CSSProperties
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 2, right: 1, bottom: 2, left: 1 }}
        >
          <YAxis hide domain={["auto", "auto"]} />
          <XAxis hide dataKey="point" />
          <Line
            className={sparklineColors[color]}
            type="linear"
            dataKey="value"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            dot={false}
            activeDot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartLegend({ series }: { series: SeriesConfig[] }) {
  return (
    <div className="mb-4 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm font-medium text-text-primary">
      {series.map((item) => (
        <div key={item.key} className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full", item.dotClassName)} />
          {item.label}
        </div>
      ))}
    </div>
  );
}

function MetricTooltip({
  active,
  label,
  payload,
  series,
  valueFormatter,
}: TooltipProps<number, string> & {
  series: SeriesConfig[];
  valueFormatter: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const seriesByKey = new Map(series.map((item) => [item.key, item]));

  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-popover">
      <div className="mb-1 font-medium text-text-primary">{label}</div>
      <div className="space-y-1">
        {payload
          .filter((item) => typeof item.value === "number")
          .map((item) => {
            const config = seriesByKey.get(item.dataKey as SeriesKey);
            return (
              <div
                key={String(item.dataKey)}
                className="flex items-center justify-between gap-4 text-text-secondary"
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      config?.dotClassName || "bg-text-muted",
                    )}
                  />
                  {config?.label || item.name}
                </span>
                <span className="font-medium text-text-primary">
                  {valueFormatter(item.value as number)}
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}

function useAppendSlide(keys: string[], horizontalInset: number) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const previousKeysRef = React.useRef<string[]>([]);
  const keysRef = React.useRef<string[]>(keys);
  const timeoutRef = React.useRef<number | null>(null);
  const frameRef = React.useRef<number | null>(null);
  const reducedMotion = usePrefersReducedMotion();
  const keySignature = keys.join("\u001f");
  const [slide, setSlide] = React.useState({
    active: false,
    drawActive: false,
    offset: 0,
  });
  keysRef.current = keys;

  React.useLayoutEffect(() => {
    if (timeoutRef.current != null) window.clearTimeout(timeoutRef.current);
    if (frameRef.current != null) window.cancelAnimationFrame(frameRef.current);

    const nextKeys = keysRef.current;
    const previousKeys = previousKeysRef.current;
    previousKeysRef.current = nextKeys;

    const canDraw = !reducedMotion && nextKeys.length >= 2;
    if (canDraw && previousKeys.length === 0) {
      setSlide({ active: false, drawActive: true, offset: 0 });
      timeoutRef.current = window.setTimeout(() => {
        setSlide({ active: false, drawActive: false, offset: 0 });
      }, 620);
      return () => {
        if (timeoutRef.current != null) window.clearTimeout(timeoutRef.current);
      };
    }

    const change = getAppendOnlySlideChange(previousKeys, nextKeys);
    if (!change || reducedMotion || !ref.current) {
      setSlide({ active: false, drawActive: false, offset: 0 });
      return undefined;
    }

    const width = Math.max(0, ref.current.clientWidth - horizontalInset);
    const pointCount = Math.max(nextKeys.length - 1, 1);
    const pointWidth = width / pointCount;
    const offset = Math.min(width, pointWidth * change.appendedCount);

    if (offset <= 0) {
      setSlide({ active: false, drawActive: false, offset: 0 });
      return undefined;
    }

    setSlide({ active: false, drawActive: false, offset });
    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = window.requestAnimationFrame(() => {
        setSlide({ active: true, drawActive: false, offset: 0 });
      });
    });
    timeoutRef.current = window.setTimeout(() => {
      setSlide({ active: false, drawActive: false, offset: 0 });
    }, 420);

    return () => {
      if (timeoutRef.current != null) window.clearTimeout(timeoutRef.current);
      if (frameRef.current != null)
        window.cancelAnimationFrame(frameRef.current);
    };
  }, [horizontalInset, keySignature, reducedMotion]);

  return {
    ...slide,
    ref,
  };
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = React.useState(false);

  React.useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = () => setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
