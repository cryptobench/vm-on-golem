"use client";

import React from "react";
import { RiCloseLine } from "@remixicon/react";
import { Modal } from "./Modal";
import { cn } from "./cn";

type DialogScaffoldProps = {
  open?: boolean;
  title: string;
  description?: string;
  closeLabel: string;
  onClose: () => void;
  closeDisabled?: boolean;
  sidebar?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
};

export function DialogScaffold({
  open = true,
  title,
  description,
  closeLabel,
  onClose,
  closeDisabled,
  sidebar,
  footer,
  children,
}: DialogScaffoldProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="6xl"
      className="flex h-[calc(100vh-2rem)] max-h-[calc(100vh-2rem)] flex-col overflow-hidden rounded-lg"
    >
      <DialogHeader
        title={title}
        description={description}
        closeLabel={closeLabel}
        closeDisabled={closeDisabled}
        onClose={onClose}
      />
      <div
        className={cn(
          "mt-6 grid min-h-0 flex-1 grid-cols-1 overflow-hidden border-t border-border",
          sidebar ? "md:grid-cols-[13rem_minmax(0,1fr)]" : undefined,
        )}
      >
        {sidebar}
        <main className="min-h-0 min-w-0 overflow-y-auto px-6 py-6 sm:px-8">
          {children}
        </main>
      </div>
      {footer}
    </Modal>
  );
}

function DialogHeader({
  title,
  description,
  closeLabel,
  closeDisabled,
  onClose,
}: {
  title: string;
  description?: string;
  closeLabel: string;
  closeDisabled?: boolean;
  onClose: () => void;
}) {
  return (
    <div className="shrink-0 px-6 pt-6 sm:px-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">{title}</h2>
          {description ? (
            <p className="mt-1 text-sm text-text-secondary">{description}</p>
          ) : null}
        </div>
        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-md text-text-secondary hover:bg-surface-muted hover:text-text-primary"
          aria-label={closeLabel}
          onClick={onClose}
          disabled={closeDisabled}
        >
          <RiCloseLine className="h-5 w-5" aria-hidden />
        </button>
      </div>
    </div>
  );
}
