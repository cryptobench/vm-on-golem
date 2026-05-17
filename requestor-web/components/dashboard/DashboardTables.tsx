"use client";

import React from "react";
import Link from "next/link";
import { RiMoreFill, RiUbuntuLine, RiWindowsLine } from "@remixicon/react";
import type { Rental, VMResources } from "../../lib/api";
import { vmDetailsHref } from "../../lib/routes";
import { humanDuration } from "../../lib/streams";
import { useVmLive } from "../../hooks/useVmLive";
import { sshEndpointLabel } from "../../lib/providerConnection";
import { DashboardStatus } from "./DashboardStatus";

export type DashboardStreamRow = {
  rental: Rental;
  remainingSeconds: number | null;
  spentSoFar: string | null;
  remainingBalance: string | null;
  hourlyRate: string | null;
  tokenSymbol: string;
  status: "Active" | "Terminated" | "Unavailable";
};

function shortId(value?: string | number | null) {
  if (value == null || value === "") return "-";
  const text = String(value);
  return text.length > 13 ? `${text.slice(0, 6)}...${text.slice(-4)}` : text;
}

function resourceValue(resources: VMResources | undefined, key: keyof VMResources) {
  const value = resources?.[key];
  return value == null ? "-" : String(value);
}

function platformLabel(platform?: string | null) {
  const value = platform || "Linux";
  const lower = value.toLowerCase();
  if (lower.includes("windows")) return { Icon: RiWindowsLine, label: "Windows" };
  return { Icon: RiUbuntuLine, label: value };
}

export function ActiveVmsTable({ rentals }: { rentals: Rental[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs font-medium text-text-secondary">
            <th className="py-4 pr-4">VM Name</th>
            <th className="px-4 py-4">Status</th>
            <th className="px-4 py-4">Provider ID</th>
            <th className="px-4 py-4">VM ID</th>
            <th className="px-4 py-4">Platform</th>
            <th className="px-4 py-4">vCPU</th>
            <th className="px-4 py-4">RAM</th>
            <th className="px-4 py-4">Storage</th>
            <th className="px-4 py-4">SSH Endpoint</th>
            <th className="py-4 pl-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rentals.map((rental) => (
            <ActiveVmRow key={rental.vm_id} rental={rental} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActiveVmRow({ rental }: { rental: Rental }) {
  const live = useVmLive(
    rental.provider_endpoint_url,
    rental.vm_id,
    rental.creation_job_id,
  );
  const liveLifecycle = live.state.lifecycle;
  const sshEndpoint = sshEndpointLabel({
    access: live.state.access,
    provider: live.state.providerInfo,
    rental,
  });
  const platform = platformLabel(rental.platform);
  const PlatformIcon = platform.Icon;
  const status = String(liveLifecycle?.status || rental.status);

  return (
    <tr className="border-b border-border last:border-b-0">
      <td className="py-4 pr-4 font-medium text-text-primary">
        <Link className="hover:text-primary" href={vmDetailsHref(rental.vm_id)}>
          {rental.name}
        </Link>
      </td>
      <td className="px-4 py-4"><DashboardStatus status={status} /></td>
      <td className="px-4 py-4 font-mono text-text-primary">{shortId(rental.provider_id)}</td>
      <td className="px-4 py-4 font-mono text-text-primary">{shortId(rental.vm_id)}</td>
      <td className="px-4 py-4">
        <span className="inline-flex items-center gap-2">
          <PlatformIcon className="h-4 w-4 text-primary" aria-hidden />
          {platform.label}
        </span>
      </td>
      <td className="px-4 py-4">{resourceValue(rental.resources, "cpu")}</td>
      <td className="px-4 py-4">{resourceValue(rental.resources, "memory")} GB</td>
      <td className="px-4 py-4">{resourceValue(rental.resources, "storage")} GB</td>
      <td className="px-4 py-4 font-mono text-text-primary">{sshEndpoint}</td>
      <td className="py-4 pl-4 text-right">
        <button className="rounded-md p-1 text-text-primary hover:bg-surface-muted" type="button" aria-label={`Actions for ${rental.name}`}>
          <RiMoreFill className="h-5 w-5" aria-hidden />
        </button>
      </td>
    </tr>
  );
}

export function ActiveStreamsTable({ rows }: { rows: DashboardStreamRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs font-medium text-text-secondary">
            <th className="py-4 pr-4">Stream ID</th>
            <th className="px-4 py-4">VM Name</th>
            <th className="px-4 py-4">Recipient / Provider ID</th>
            <th className="px-4 py-4">Remaining Time</th>
            <th className="px-4 py-4">Spent So Far</th>
            <th className="px-4 py-4">Remaining Balance</th>
            <th className="px-4 py-4">Hourly Rate</th>
            <th className="px-4 py-4">Token</th>
            <th className="px-4 py-4">Status</th>
            <th className="py-4 pl-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.rental.vm_id}-${row.rental.stream_id}`} className="border-b border-border last:border-b-0">
              <td className="py-4 pr-4 font-mono text-text-primary">{shortId(row.rental.stream_id)}</td>
              <td className="px-4 py-4 font-medium text-text-primary">{row.rental.name}</td>
              <td className="px-4 py-4 font-mono">{shortId(row.rental.provider_id)}</td>
              <td className="px-4 py-4">{row.remainingSeconds == null ? "-" : humanDuration(row.remainingSeconds)}</td>
              <td className="px-4 py-4">{row.spentSoFar || "-"}</td>
              <td className="px-4 py-4">{row.remainingBalance || "-"}</td>
              <td className="px-4 py-4">{row.hourlyRate || "-"}</td>
              <td className="px-4 py-4">{row.tokenSymbol}</td>
              <td className="px-4 py-4"><DashboardStatus status={row.status} /></td>
              <td className="py-4 pl-4 text-right">
                <button className="rounded-md p-1 text-text-primary hover:bg-surface-muted" type="button" aria-label={`Actions for stream ${row.rental.stream_id}`}>
                  <RiMoreFill className="h-5 w-5" aria-hidden />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
