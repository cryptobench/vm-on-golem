"use client";

import React from "react";
import {
  RiCameraLine,
  RiDeleteBinLine,
  RiExternalLinkLine,
  RiRestartLine,
} from "@remixicon/react";
import { Spinner } from "@golem/ui";
import { DetailPanel, IconButton, PanelTitle } from "./VmDetailPrimitives";

export type VmSnapshotRow = {
  name: string;
  comment?: string | null;
  created_at?: string | null;
};

export function VmSnapshotsPanel({
  snapshots,
  stopped,
  disabled,
  busy,
  onCreate,
  onRestore,
  onDelete,
}: {
  snapshots: VmSnapshotRow[];
  stopped: boolean;
  disabled?: boolean;
  busy?: string | null;
  onCreate: () => void;
  onRestore: (name: string) => void;
  onDelete: (name: string) => void;
}) {
  const createButton = (
    <button
      type="button"
      className="btn btn-secondary gap-2"
      onClick={onCreate}
      disabled={disabled || !!busy || !stopped}
    >
      {busy === "create" ? (
        <Spinner className="h-4 w-4" />
      ) : (
        <RiCameraLine className="h-4 w-4" aria-hidden />
      )}
      Create snapshot
    </button>
  );

  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Snapshots"
        hint="Snapshots can be created and restored only when the VM is stopped."
        trailing={
          <div className="flex items-center gap-2">
            {snapshots.length ? createButton : null}
          </div>
        }
      />

      {snapshots.length ? (
        <div className="mt-4 overflow-hidden rounded-lg border border-border">
          <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(10rem,0.9fr)_5rem] bg-surface-muted px-3 py-2 text-xs font-medium text-text-muted">
            <div>Snapshot name</div>
            <div>Comment</div>
            <div>Created at</div>
            <div className="text-right">Actions</div>
          </div>
          <div className="divide-y divide-border">
            {snapshots.map((snapshot) => (
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
                    disabled={disabled || !!busy || !stopped}
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
                    disabled={disabled || !!busy}
                  >
                    {busy === `delete:${snapshot.name}` ? (
                      <Spinner className="h-4 w-4" />
                    ) : (
                      <RiDeleteBinLine className="h-4 w-4" aria-hidden />
                    )}
                  </IconButton>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-5 flex min-h-56 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-surface px-4 py-8 text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary-soft text-primary">
            <RiCameraLine className="h-9 w-9" aria-hidden />
          </div>
          <h4 className="mt-4 text-base font-semibold text-text-primary">
            No snapshots yet
          </h4>
          <p className="mt-2 max-w-xs text-sm leading-5 text-text-secondary">
            Create a snapshot to save the current state of this VM.
          </p>
          <div className="mt-5">{createButton}</div>
        </div>
      )}

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
