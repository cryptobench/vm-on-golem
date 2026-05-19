"use client";

import React from "react";
import { RiBroadcastLine, RiStackLine } from "@remixicon/react";
import { Sparkline as UiSparkline } from "@golem/ui";

type SummaryVisual = "vms" | "streams" | "spend";

function Sparkline({ data }: { data: number[] }) {
  const values = data.length > 1 ? data : [0, 0];

  return (
    <UiSparkline
      className="h-16 w-32"
      data={values.map((value, index) => ({
        label: String(index + 1),
        value,
      }))}
    />
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
