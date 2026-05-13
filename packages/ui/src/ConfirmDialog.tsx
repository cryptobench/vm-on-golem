"use client";
import React from "react";
import { Modal } from "./Modal";
import { Spinner } from "./Spinner";

export function ConfirmDialog({
  open,
  title,
  description,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  busy = false,
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  children?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  busy?: boolean;
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} onClose={onCancel} size="md">
      <div className="px-5 py-4">
        <div className="text-lg font-semibold">{title}</div>
        {description && <div className="mt-2 text-sm text-gray-700">{description}</div>}
        {children}
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>{cancelLabel}</button>
          <button className={danger ? "btn btn-danger" : "btn btn-primary"} onClick={() => onConfirm()} disabled={busy}>
            {busy ? (<><Spinner className="h-4 w-4" /> {confirmLabel}</>) : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}

