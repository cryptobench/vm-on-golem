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
import { cn } from "./cn";

export type ChartPoint = {
  label: string;
  value: number;
  secondaryValue?: number;
};

export type ChartDatum = Record<string, string | number | null | undefined>;

export type ChartSeries = {
  key: string;
  label: string;
  colorClassName: string;
  dotClassName?: string;
};

export function LineAreaChart({
  data,
  height = 220,
  yUnit,
  valueFormatter,
  secondary = false,
  className,
}: {
  data: ChartPoint[];
  height?: number;
  yUnit?: string;
  valueFormatter?: (value: number) => string;
  secondary?: boolean;
  className?: string;
}) {
  const chartData: ChartDatum[] = data.map((point) => ({
    label: point.label,
    value: point.value,
    secondaryValue: point.secondaryValue,
  }));
  const series: ChartSeries[] = [
    {
      key: "value",
      label: "value",
      colorClassName: "text-primary",
      dotClassName: "bg-primary",
    },
  ];

  if (secondary) {
    series.push({
      key: "secondaryValue",
      label: "secondary",
      colorClassName: "text-success",
      dotClassName: "bg-success",
    });
  }

  return (
    <SlidingLineChart
      className={className}
      data={chartData}
      series={series}
      xKey="label"
      animationKey={(point) => String(point.label)}
      valueFormatter={valueFormatter ?? ((value) => `${value}${yUnit ?? ""}`)}
      height={height}
      showLegend={false}
    />
  );
}

export function Sparkline({
  data,
  className,
  colorClassName = "text-primary",
}: {
  data: ChartPoint[];
  className?: string;
  colorClassName?: string;
}) {
  const chartData = data.map((point) => ({
    label: point.label,
    value: point.value,
  }));

  return (
    <SlidingSparkline
      className={cn("h-8 w-20", className)}
      colorClassName={colorClassName}
      data={chartData}
      xKey="label"
      dataKey="value"
      animationKey={(point) => point.label}
    />
  );
}

export function SlidingLineChart<TData extends ChartDatum>({
  className,
  data,
  series,
  xKey,
  animationKey,
  valueFormatter = String,
  minValue,
  yAxisWidth = 56,
  height,
  showLegend = true,
}: {
  className?: string;
  data: TData[];
  series: ChartSeries[];
  xKey: keyof TData & string;
  animationKey?: (row: TData) => string;
  valueFormatter?: (value: number) => string;
  minValue?: number;
  yAxisWidth?: number;
  height?: number;
  showLegend?: boolean;
}) {
  const slide = useAppendSlide(
    data.map((row, index) =>
      animationKey ? animationKey(row) : String(row[xKey] ?? index),
    ),
    yAxisWidth + 40,
  );

  return (
    <div
      ref={slide.ref}
      className={cn("golem-sliding-chart flex min-h-0 flex-col", className)}
      data-slide-active={slide.active ? "true" : "false"}
      data-draw-active={slide.drawActive ? "true" : "false"}
      style={
        {
          height,
          "--golem-chart-slide-x": `${slide.offset}px`,
        } as React.CSSProperties
      }
    >
      {showLegend ? <ChartLegend series={series} /> : null}
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
              dataKey={xKey}
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
                  series={series}
                  valueFormatter={valueFormatter}
                />
              }
            />
            <Legend wrapperStyle={{ display: "none" }} />
            {series.map((item) => (
              <Line
                key={item.key}
                className={item.colorClassName}
                type="linear"
                dataKey={item.key}
                name={item.label}
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

export function SlidingSparkline<TData extends ChartDatum>({
  className,
  data,
  colorClassName = "text-primary",
  dataKey = "value",
  xKey = "point",
  animationKey,
}: {
  className?: string;
  data: TData[];
  colorClassName?: string;
  dataKey?: keyof TData & string;
  xKey?: keyof TData & string;
  animationKey?: (row: TData) => string;
}) {
  const slide = useAppendSlide(
    data.map((row, index) =>
      animationKey ? animationKey(row) : String(row[xKey] ?? index),
    ),
    2,
  );

  return (
    <div
      ref={slide.ref}
      className={cn("golem-sliding-chart", className)}
      data-slide-active={slide.active ? "true" : "false"}
      data-draw-active={slide.drawActive ? "true" : "false"}
      style={
        {
          "--golem-chart-slide-x": `${slide.offset}px`,
        } as React.CSSProperties
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 2, right: 1, bottom: 2, left: 1 }}
        >
          <YAxis hide domain={["auto", "auto"]} />
          <XAxis hide dataKey={xKey} />
          <Line
            className={colorClassName}
            type="linear"
            dataKey={dataKey}
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

function ChartLegend({ series }: { series: ChartSeries[] }) {
  return (
    <div className="mb-4 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm font-medium text-text-primary">
      {series.map((item) => (
        <div key={item.key} className="flex items-center gap-2">
          <span
            className={cn("h-2 w-2 rounded-full", item.dotClassName)}
            style={item.dotClassName ? undefined : { color: "currentColor" }}
          />
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
  series: ChartSeries[];
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
            const config = seriesByKey.get(String(item.dataKey));
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

export function getAppendOnlySlideChange(
  previousKeys: string[],
  nextKeys: string[],
): { appendedCount: number; droppedCount: number } | null {
  if (previousKeys.length === 0 || nextKeys.length === 0) return null;
  if (hasDuplicateKeys(previousKeys) || hasDuplicateKeys(nextKeys)) return null;

  const maxOverlap = Math.min(previousKeys.length, nextKeys.length);
  for (let overlap = maxOverlap; overlap >= 1; overlap -= 1) {
    const previousStart = previousKeys.length - overlap;
    let matches = true;
    for (let index = 0; index < overlap; index += 1) {
      if (previousKeys[previousStart + index] !== nextKeys[index]) {
        matches = false;
        break;
      }
    }

    if (!matches) continue;

    const appendedCount = nextKeys.length - overlap;
    if (appendedCount <= 0) return null;

    const minRequiredOverlap =
      previousKeys.length >= 3 && nextKeys.length >= 3 ? 3 : 1;
    if (overlap < minRequiredOverlap) return null;

    return {
      appendedCount,
      droppedCount: previousKeys.length - overlap,
    };
  }

  return null;
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

function hasDuplicateKeys(keys: string[]) {
  return new Set(keys).size !== keys.length;
}
