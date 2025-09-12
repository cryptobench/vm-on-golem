"use client";
import React from "react";
import { Dialog, DialogPanel } from "@tremor/react";
import { cn } from "./cn";

type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl';

export function Modal({ open, onClose, children, className, labelledBy, size }: { open: boolean; onClose: () => void; children: React.ReactNode; className?: string; labelledBy?: string; size?: ModalSize }) {
  const widthClass = (
    size === 'sm' ? 'sm:max-w-sm' :
    size === 'md' ? 'sm:max-w-md' :
    size === 'lg' ? 'sm:max-w-lg' :
    size === 'xl' ? 'sm:max-w-xl' :
    size === '2xl' ? 'sm:max-w-2xl' :
    size === '3xl' ? 'sm:max-w-3xl' :
    'sm:max-w-lg'
  );
  return (
    <Dialog open={open} onClose={onClose} aria-labelledby={labelledBy} className="z-[100]">
      <DialogPanel
        className={cn(
          "w-full max-h-[90vh] overflow-y-auto rounded-xl bg-white shadow-lg ring-1 ring-gray-200",
          widthClass,
          className,
        )}
      >
        {children}
      </DialogPanel>
    </Dialog>
  );
}
