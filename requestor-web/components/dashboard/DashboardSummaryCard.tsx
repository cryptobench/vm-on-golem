"use client";

import React from "react";
import { RiBroadcastLine, RiStackLine } from "@remixicon/react";

type SummaryVisual = "vms" | "streams" | "spend";

function Sparkline({ data }: { data: number[] }) {
  const values = data.length > 1 ? data : [0, 0];
  const width = 128;
  const height = 64;
  const left = 4;
  const right = 124;
  const top = 12;
  const bottom = 50;
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const range = max - min;
  const points = values.map((value, index) => {
    const x = left + ((right - left) * index) / Math.max(1, values.length - 1);
    const y = range === 0 ? bottom : bottom - ((value - min) / range) * (bottom - top);
    return { x, y };
  });
  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L ${right} ${height} L ${left} ${height} Z`;

  return (
    <svg className="h-16 w-32 text-primary" viewBox="0 0 128 64" aria-hidden>
      <path d={areaPath} fill="currentColor" opacity="0.06" />
      <path d={linePath} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
    </svg>
  );
}

function Visual({ type, chartData }: { type: SummaryVisual; chartData?: number[] }) {
  if (type === "spend") return <Sparkline data={chartData || [0, 0]} />;

  const Icon = type === "vms" ? RiStackLine : RiBroadcastLine;
  return (
    <div className="flex h-16 w-24 items-center justify-center rounded-full bg-primary-soft text-primary opacity-80">
      <Icon className="h-10 w-10" aria-hidden />
    </div>
  );
}

export function DashboardSummaryCard({
  title,
  value,
  meta,
  visual,
  chartData,
}: {
  title: string;
  value: string;
  meta: React.ReactNode;
  visual: SummaryVisual;
  chartData?: number[];
}) {
  return (
    <section className="rounded-lg border border-border bg-surface p-5 shadow-sm">
      <div className="flex min-h-20 items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-medium text-text-secondary">{title}</div>
          <div className="mt-2 truncate text-2xl font-semibold tracking-tight text-text-primary">{value}</div>
          <div className="mt-3 text-sm text-text-secondary">{meta}</div>
        </div>
        <div className="hidden shrink-0 sm:block">
          <Visual type={visual} chartData={chartData} />
        </div>
      </div>
    </section>
  );
}
