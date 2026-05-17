"use client";

import React from "react";
import type { RequestorVmModel } from "../../lib/requestorVmModel";
import { RentalRowWithData } from "./RentalRowWithData";

const HEADERS = [
  "VM Name",
  "Status",
  "Provider ID",
  "Country",
  "Platform",
  "vCPU",
  "RAM",
  "Storage",
];

type RentalsTableProps = {
  title: string;
  subtitle: string;
  count: number;
  vms: RequestorVmModel[];
  timeColumnLabel: string;
  terminated?: boolean;
};

export function RentalsTable({
  title,
  subtitle,
  count,
  vms,
  timeColumnLabel,
  terminated,
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
            </tr>
          </thead>
          <tbody>
            {vms.map((vm) => (
              <RentalRowWithData
                key={vm.rental.vm_id}
                vm={vm}
                terminated={terminated}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
