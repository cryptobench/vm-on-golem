"use client";

import React from "react";
import {
  RiCheckboxCircleFill,
  RiComputerLine,
  RiGlobalLine,
  RiServerLine,
} from "@remixicon/react";
import { countryFlagEmoji, countryFullName } from "../../../lib/intl";
import type { VMResources } from "../../../lib/api";
import {
  CopyInline,
  DetailPanel,
  InfoField,
  shortAddress,
} from "./VmDetailPrimitives";

export function VmOverviewPanel({
  providerId,
  vmId,
  country,
  platform,
  providerIp,
  sshPort,
  resources,
  onCopy,
}: {
  providerId: string;
  vmId: string;
  country?: string | null;
  platform?: string | null;
  providerIp?: string | null;
  sshPort?: number | null;
  resources?: VMResources | null;
  onCopy: (value: string) => void;
}) {
  return (
    <DetailPanel className="vm-page-enter">
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <InfoField label="Provider ID" className="xl:border-r xl:border-border xl:pr-6">
          <CopyInline
            value={providerId}
            display={shortAddress(providerId)}
            onCopy={onCopy}
          />
        </InfoField>
        <InfoField label="Location" className="xl:border-r xl:border-border xl:pr-6">
          <span className="inline-flex min-w-0 items-center gap-2">
            <span className="text-lg leading-none" aria-hidden>
              {country ? countryFlagEmoji(country) : "-"}
            </span>
            <span className="truncate">
              {country ? countryFullName(country) : "Unknown region"}
            </span>
          </span>
        </InfoField>
        <InfoField label="Platform" className="xl:border-r xl:border-border xl:pr-6">
          <span className="inline-flex items-center gap-2">
            <RiComputerLine className="h-4 w-4 text-text-muted" aria-hidden />
            <span>{platform || "Unknown"}</span>
          </span>
        </InfoField>
        <InfoField label="Resources">
          <span className="inline-flex flex-wrap gap-x-2 gap-y-1">
            <span>{resources?.cpu || "-"} vCPU</span>
            <span aria-hidden>&middot;</span>
            <span>{resources?.memory || "-"} GB RAM</span>
            <span aria-hidden>&middot;</span>
            <span>{resources?.storage || "-"} GB Storage</span>
          </span>
        </InfoField>
        <InfoField label="VM ID" className="xl:border-r xl:border-border xl:pr-6">
          <CopyInline value={vmId} display={shortAddress(vmId)} onCopy={onCopy} />
        </InfoField>
        <InfoField label="Provider IP" className="xl:border-r xl:border-border xl:pr-6">
          <span className="inline-flex items-center gap-2">
            <RiGlobalLine className="h-4 w-4 text-text-muted" aria-hidden />
            <CopyInline value={providerIp} onCopy={onCopy} />
          </span>
        </InfoField>
        <InfoField label="SSH Port" className="xl:border-r xl:border-border xl:pr-6">
          <span className="inline-flex items-center gap-2">
            {sshPort ? (
              <RiCheckboxCircleFill
                className="h-4 w-4 text-success"
                aria-hidden
              />
            ) : (
              <RiServerLine className="h-4 w-4 text-text-muted" aria-hidden />
            )}
            <span>{sshPort || "-"}</span>
            {sshPort && <span className="text-xs text-success">(Available)</span>}
          </span>
        </InfoField>
      </div>
    </DetailPanel>
  );
}
