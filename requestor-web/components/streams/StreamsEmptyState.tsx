"use client";

import React from "react";
import { RiExternalLinkLine, RiInformationLine, RiWallet3Line } from "@remixicon/react";
import { RentVmButton } from "../create/RentVmButton";

const PAYMENT_STREAMS_DOCS_URL = "";

type StreamsEmptyStateProps = {
  title: string;
  description: string;
  showRentAction?: boolean;
};

export function StreamsEmptyState({
  title,
  description,
  showRentAction = true,
}: StreamsEmptyStateProps) {
  return (
    <section className="streams-empty rounded-lg border border-border bg-surface px-6 py-16 text-center shadow-soft">
      <div className="mx-auto flex max-w-md flex-col items-center">
        <div className="streams-empty__icon flex h-24 w-24 items-center justify-center">
          <RiWallet3Line className="h-12 w-12 text-brand-400" aria-hidden />
        </div>
        <h2 className="mt-8 text-xl font-semibold text-text-primary">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-text-secondary">{description}</p>
        {showRentAction ? <RentVmButton className="mt-8" /> : null}
        <a
          className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-primary transition hover:text-primary-hover"
          href={PAYMENT_STREAMS_DOCS_URL}
          rel="noreferrer"
          target="_blank"
        >
          <RiInformationLine className="h-4 w-4" aria-hidden />
          Learn more about payment streams
          <RiExternalLinkLine className="h-4 w-4" aria-hidden />
        </a>
      </div>
    </section>
  );
}

export function StreamsInfoBanner() {
  return (
    <aside className="flex flex-col gap-3 rounded-lg bg-primary-soft px-5 py-4 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <RiInformationLine className="h-5 w-5 shrink-0 text-primary" aria-hidden />
        <span>Stream data is updated automatically every 15 seconds. Spend, totals, and remaining time are live.</span>
      </div>
      <a
        className="inline-flex items-center gap-2 font-medium text-primary transition hover:text-primary-hover"
        href={PAYMENT_STREAMS_DOCS_URL}
        rel="noreferrer"
        target="_blank"
      >
        Learn more about payment streams
        <RiExternalLinkLine className="h-4 w-4" aria-hidden />
      </a>
    </aside>
  );
}
