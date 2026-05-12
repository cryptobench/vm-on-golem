"use client";

import React from "react";
import Link from "next/link";
import { RiBox3Line, RiExternalLinkLine } from "@remixicon/react";
import { RentVmButton } from "../create/RentVmButton";

type RentalsEmptyStateProps = {
  title: string;
  description: string;
  showSecondaryAction?: boolean;
  onClearSearch?: () => void;
};

export function RentalsEmptyState({
  title,
  description,
  showSecondaryAction,
  onClearSearch,
}: RentalsEmptyStateProps) {
  return (
    <section className="rentals-empty flex min-h-[34rem] items-center justify-center rounded-lg border border-border bg-surface px-6 py-12 shadow-soft">
      <div className="mx-auto flex max-w-xl flex-col items-center text-center">
        <div className="rentals-empty__icon mb-8 flex h-36 w-36 items-center justify-center text-primary">
          <RiBox3Line className="h-20 w-20" aria-hidden />
        </div>
        <h2 className="text-2xl font-semibold tracking-normal">{title}</h2>
        <p className="mt-3 text-sm text-text-secondary">{description}</p>
        <p className="mt-1 text-sm font-medium text-text-secondary">
          {showSecondaryAction
            ? "Filters can hide VMs that still belong to this project."
            : "Create or rent your first VM."}
        </p>
        <div className="mt-8">
          {showSecondaryAction ? (
            <button
              className="btn btn-secondary text-primary ring-primary"
              onClick={onClearSearch}
              type="button"
            >
              Clear search
            </button>
          ) : (
            <RentVmButton className="px-7" />
          )}
        </div>
        {!showSecondaryAction && (
          <Link
            className="mt-7 inline-flex items-center gap-2 text-sm font-medium text-primary transition hover:text-primary-hover"
            href="/providers"
          >
            <RiExternalLinkLine className="h-4 w-4" aria-hidden />
            Browse providers
          </Link>
        )}
      </div>
    </section>
  );
}
