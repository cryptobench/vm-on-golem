"use client";

import React from "react";
import Link from "next/link";
import { RiArrowRightSLine } from "@remixicon/react";

export function DashboardSection({
  title,
  href,
  linkLabel,
  children,
}: {
  title: string;
  href?: string;
  linkLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border bg-surface p-4 shadow-sm sm:p-5">
      <div className="flex items-center justify-between gap-4 border-b border-border pb-3">
        <h2 className="text-lg font-semibold tracking-tight text-text-primary">{title}</h2>
        {href && linkLabel && (
          <Link className="inline-flex items-center gap-1 text-sm font-medium text-primary" href={href}>
            {linkLabel}
            <RiArrowRightSLine className="h-5 w-5" aria-hidden />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
