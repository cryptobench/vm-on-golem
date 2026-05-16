"use client";
import React from "react";
import { Dialog, DialogBackdrop, DialogPanel } from "@headlessui/react";
import { cn } from "./cn";

type ModalSize = "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "6xl";

export function Modal({
  open,
  onClose,
  children,
  className,
  labelledBy,
  size,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
  labelledBy?: string;
  size?: ModalSize;
}) {
  const widthClass =
    size === "sm"
      ? "sm:max-w-sm"
      : size === "md"
        ? "sm:max-w-md"
        : size === "lg"
          ? "sm:max-w-lg"
          : size === "xl"
            ? "sm:max-w-xl"
            : size === "2xl"
              ? "sm:max-w-2xl"
              : size === "3xl"
                ? "sm:max-w-3xl"
                : size === "6xl"
                  ? "sm:max-w-6xl"
                  : "sm:max-w-lg";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby={labelledBy}
      className="relative z-[100]"
    >
      <DialogBackdrop
        transition
        className={cn(
          "fixed inset-0 bg-text-primary/45 backdrop-blur-sm",
          "motion-safe:transition motion-safe:duration-200 motion-safe:ease-out",
          "data-[closed]:bg-text-primary/0 data-[closed]:opacity-0 data-[closed]:backdrop-blur-0",
        )}
      />
      <div className="fixed inset-0 w-screen overflow-y-auto">
        <div className="flex min-h-full items-center justify-center p-4">
          <DialogPanel
            transition
            className={cn(
              "w-full max-h-[90vh] overflow-y-auto rounded-xl bg-surface shadow-lg ring-1 ring-border",
              "will-change-transform motion-safe:transition motion-safe:duration-200 motion-safe:ease-out",
              "data-[closed]:translate-y-2 data-[closed]:scale-95 data-[closed]:opacity-0",
              "sm:data-[closed]:translate-y-0 sm:data-[closed]:scale-[0.98]",
              widthClass,
              className,
            )}
          >
            {children}
          </DialogPanel>
        </div>
      </div>
    </Dialog>
  );
}
