"use client";

import React from "react";
import type { Rental } from "../../lib/api";
import { RentalRowWithData } from "./RentalRowWithData";

const HEADERS = [
  "VM Name",
  "Status",
  "VM ID",
  "Provider ID",
  "Country",
  "SSH Endpoint",
  "Platform",
  "vCPU",
  "RAM",
  "Storage",
  "Stream ID",
];

type RentalsTableProps = {
  title: string;
  subtitle: string;
  count: number;
  rentals: Rental[];
  busyId: string | null;
  timeColumnLabel: string;
  terminated?: boolean;
  onCopySSH?: (rental: Rental) => void;
  onStart?: (rental: Rental) => void;
  onStop?: (rental: Rental) => void;
  onDestroy?: (rental: Rental) => void;
};

export function RentalsTable({
  title,
  subtitle,
  count,
  rentals,
  busyId,
  timeColumnLabel,
  terminated,
  onCopySSH,
  onStart,
  onStop,
  onDestroy,
}: RentalsTableProps) {
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface shadow-soft">
      <div className="flex items-center justify-between gap-4 border-b border-border px-4 py-4 sm:px-5">
        <div>
          <h2 className="text-base font-semibold">
            {title} <span className="text-text-secondary">({count})</span>
          </h2>
          <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="table min-w-full">
          <thead className="bg-surface-muted">
            <tr>
              {HEADERS.map((header) => (
                <th
                  className="th whitespace-nowrap py-3 normal-case tracking-normal"
                  key={header}
                >
                  {header}
                </th>
              ))}
              <th className="th whitespace-nowrap py-3 normal-case tracking-normal">
                {timeColumnLabel}
              </th>
              <th className="th whitespace-nowrap py-3 text-right normal-case tracking-normal">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {rentals.map((rental) => (
              <RentalRowWithData
                key={rental.vm_id}
                rental={rental}
                busy={busyId === rental.vm_id}
                terminated={terminated}
                onCopySSH={onCopySSH}
                onStart={onStart}
                onStop={onStop}
                onDestroy={onDestroy}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
