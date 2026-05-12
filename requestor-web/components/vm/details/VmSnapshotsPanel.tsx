"use client";

import React from "react";
import {
  RiCameraLine,
  RiDeleteBinLine,
  RiExternalLinkLine,
  RiRefreshLine,
  RiRestartLine,
} from "@remixicon/react";
import { Spinner } from "../../ui/Spinner";
import { DetailPanel, IconButton, PanelTitle } from "./VmDetailPrimitives";

export type VmSnapshotRow = {
  name: string;
  comment?: string | null;
  created_at?: string | null;
};

export function VmSnapshotsPanel({
  snapshots,
  stopped,
  busy,
  onCreate,
  onRestore,
  onDelete,
  onRefresh,
}: {
  snapshots: VmSnapshotRow[];
  stopped: boolean;
  busy?: string | null;
  onCreate: () => void;
  onRestore: (name: string) => void;
  onDelete: (name: string) => void;
  onRefresh: () => void;
}) {
  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Snapshots"
        hint="Snapshots can be created and restored only when the VM is stopped."
        trailing={
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn btn-secondary gap-2"
              onClick={onCreate}
              disabled={!!busy || !stopped}
            >
              {busy === "create" ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <RiCameraLine className="h-4 w-4" aria-hidden />
              )}
              Create snapshot
            </button>
            <IconButton label="Refresh snapshots" onClick={onRefresh} disabled={!!busy}>
              <RiRefreshLine className="h-5 w-5" aria-hidden />
            </IconButton>
          </div>
        }
      />
      <p className="mt-1 text-sm text-text-secondary">
        Snapshots are only available when the VM is stopped.
      </p>

      <div className="mt-4 overflow-hidden rounded-lg border border-border">
        <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(10rem,0.9fr)_5rem] bg-surface-muted px-3 py-2 text-xs font-medium text-text-muted">
          <div>Snapshot name</div>
          <div>Comment</div>
          <div>Created at</div>
          <div className="text-right">Actions</div>
        </div>
        <div className="divide-y divide-border">
          {snapshots.length ? (
            snapshots.map((snapshot) => (
              <div
                key={snapshot.name}
                className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(10rem,0.9fr)_5rem] items-center gap-3 px-3 py-3 text-sm"
              >
                <div className="min-w-0 truncate font-medium text-text-primary">
                  {snapshot.name}
                </div>
                <div className="min-w-0 truncate text-text-secondary">
                  {snapshot.comment || "-"}
                </div>
                <div className="min-w-0 truncate text-text-secondary">
                  {formatSnapshotDate(snapshot.created_at)}
                </div>
                <div className="flex justify-end gap-1">
                  <IconButton
                    label={`Restore ${snapshot.name}`}
                    className="h-8 w-8"
                    onClick={() => onRestore(snapshot.name)}
                    disabled={!!busy || !stopped}
                  >
                    {busy === `restore:${snapshot.name}` ? (
                      <Spinner className="h-4 w-4" />
                    ) : (
                      <RiRestartLine className="h-4 w-4" aria-hidden />
                    )}
                  </IconButton>
                  <IconButton
                    label={`Delete ${snapshot.name}`}
                    className="h-8 w-8"
                    onClick={() => onDelete(snapshot.name)}
                    disabled={!!busy}
                  >
                    {busy === `delete:${snapshot.name}` ? (
                      <Spinner className="h-4 w-4" />
                    ) : (
                      <RiDeleteBinLine className="h-4 w-4" aria-hidden />
                    )}
                  </IconButton>
                </div>
              </div>
            ))
          ) : (
            <div className="px-3 py-4 text-sm text-text-secondary">No snapshots.</div>
          )}
        </div>
      </div>

      <div className="mt-4 flex justify-end">
        <a
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:text-primary-hover"
          href="https://documentation.ubuntu.com/multipass/latest/how-to-guides/manage-instances/use-instance-snapshots/"
          target="_blank"
          rel="noreferrer"
        >
          Learn more about snapshots
          <RiExternalLinkLine className="h-4 w-4" aria-hidden />
        </a>
      </div>
    </DetailPanel>
  );
}

function formatSnapshotDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}
