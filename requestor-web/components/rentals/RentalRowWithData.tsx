"use client";

import React from "react";
import { useRouter } from "next/navigation";
import {
  useProviderInfo,
  useVmAccess,
  useVmStatusSafe,
  useVmStreamStatus,
} from "../../hooks/useApiSWR";
import type { Rental, VMResources } from "../../lib/api";
import { formatUnixSecondsDateTime } from "../../lib/time";
import { vmDetailsHref } from "../../lib/routes";
import { humanDuration } from "../../lib/streams";
import { countryFlagEmoji } from "../../lib/intl";
import { deriveVmDisplayLifecycle } from "../../lib/vmLifecycle";
import { CopyValue } from "./CopyValue";
import { RentalActionsMenu } from "./RentalActionsMenu";
import { RentalStatusPill } from "./RentalStatusPill";
import { VmPlatform } from "./VmPlatform";

type RentalRowWithDataProps = {
  rental: Rental;
  busy?: boolean;
  terminated?: boolean;
  onCopySSH?: (rental: Rental) => void;
  onStart?: (rental: Rental) => void;
  onStop?: (rental: Rental) => void;
  onDestroy?: (rental: Rental) => void;
};

function terminalStatus(status: string) {
  return status === "terminated" || status === "deleted";
}

function resourceValue(
  resources: VMResources | undefined,
  key: keyof VMResources,
) {
  const value = resources?.[key];
  return value == null ? "-" : String(value);
}

function resourceWithUnit(
  resources: VMResources | undefined,
  key: keyof VMResources,
  unit: string,
) {
  const value = resourceValue(resources, key);
  return value === "-" ? value : `${value} ${unit}`;
}

function formatEndedAt(value?: number) {
  return formatUnixSecondsDateTime(value) ?? "-";
}

export function RentalRowWithData({
  rental,
  busy,
  terminated,
  onCopySSH,
  onStart,
  onStop,
  onDestroy,
}: RentalRowWithDataProps) {
  const router = useRouter();
  const storedStatus = String(rental.status || "").toLowerCase();
  const storedTerminal = terminalStatus(storedStatus) || !!terminated;
  const { data: provider } = useProviderInfo(rental.provider_endpoint_url, {
    refreshInterval: 30000,
  });
  const { data: access, error: accessError } = useVmAccess(
    storedTerminal ? null : rental.provider_endpoint_url,
    storedTerminal ? null : rental.vm_id,
    { refreshInterval: 8000 },
  );
  const { data: status, error: statusError } = useVmStatusSafe(
    storedTerminal ? null : rental.provider_endpoint_url,
    storedTerminal ? null : rental.vm_id,
    { refreshInterval: 8000 },
  );
  const { data: stream } = useVmStreamStatus(
    storedTerminal || !rental.stream_id ? null : rental.provider_endpoint_url,
    storedTerminal || !rental.stream_id ? null : rental.vm_id,
    { refreshInterval: 15000 },
  );

  const statusPayload = ((status as { data?: unknown } | null)?.data ||
    null) as Record<string, unknown> | null;
  const lifecycleSource = statusPayload?.status
    ? statusPayload
    : (access as { status?: string } | null)?.status
      ? (access as unknown as Record<string, unknown>)
      : null;
  const lifecycle = storedTerminal
    ? deriveVmDisplayLifecycle({ lifecycle: { status: storedStatus || "terminated" } })
    : deriveVmDisplayLifecycle({
        lifecycle: lifecycleSource,
        fallback: {
          status: rental.status || (rental.ssh_port ? "running" : "creating"),
          lifecycle_stage: rental.lifecycle_stage,
          status_message: rental.status_message,
          progress: rental.progress,
          transitioning: rental.transitioning,
          next_poll_seconds: rental.next_poll_seconds,
        },
        safeStatus: status,
        statusError,
        accessError,
      });
  const liveStatus = lifecycle.status;
  const isTerminated = terminalStatus(liveStatus);
  const country = (provider as { country?: string } | null)?.country || "";
  const flag = countryFlagEmoji(country);
  const resources = ((statusPayload as { resources?: VMResources } | null)
    ?.resources || rental.resources) as VMResources | undefined;
  const platform =
    (provider as { platform?: string | null } | null)?.platform ||
    (statusPayload as { platform?: string | null } | null)?.platform ||
    rental.platform ||
    "Linux";
  const providerIp =
    (provider as { ip_address?: string | null } | null)?.ip_address ||
    rental.provider_ip ||
    (access as { ssh_host?: string | null } | null)?.ssh_host ||
    "";
  const remainingSeconds = (
    stream as { computed?: { remaining_seconds?: number | null } } | null
  )?.computed?.remaining_seconds;
  const timeValue = isTerminated
    ? formatEndedAt(rental.ended_at)
    : rental.stream_id
      ? remainingSeconds == null
        ? "Fetching"
        : humanDuration(remainingSeconds)
      : "-";

  const openDetails = () => router.push(vmDetailsHref(rental.vm_id));

  return (
    <tr
      className="vm-table-row group cursor-pointer border-t border-border bg-surface"
      onClick={openDetails}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === " " || event.key === "Enter") {
          event.preventDefault();
          openDetails();
        }
      }}
    >
      <td className="td min-w-36 py-4 font-medium">{rental.name}</td>
      <td className="td py-4">
        <RentalStatusPill status={liveStatus} />
      </td>
      <td className="td py-4">
        <CopyValue value={rental.vm_id} />
      </td>
      <td className="td py-4">
        <CopyValue value={rental.provider_id} />
      </td>
      <td className="td py-4">
        <span className="inline-flex items-center gap-2">
          {flag && <span className="text-base leading-none">{flag}</span>}
          <span>{country || "-"}</span>
        </span>
      </td>
      <td className="td py-4">
        <CopyValue value={providerIp} />
      </td>
      <td className="td py-4">
        <VmPlatform platform={platform} />
      </td>
      <td className="td py-4">{resourceValue(resources, "cpu")}</td>
      <td className="td py-4">{resourceWithUnit(resources, "memory", "GB")}</td>
      <td className="td py-4">
        {resourceWithUnit(resources, "storage", "GB")}
      </td>
      <td className="td py-4">
        <CopyValue value={rental.stream_id} />
      </td>
      <td className="td min-w-32 py-4 text-text-secondary">{timeValue}</td>
      <td className="td py-4">
        <RentalActionsMenu
          rental={rental}
          status={liveStatus}
          busy={busy}
          onView={openDetails}
          onCopySSH={onCopySSH}
          onStart={onStart}
          onStop={onStop}
          onDestroy={onDestroy}
        />
      </td>
    </tr>
  );
}
