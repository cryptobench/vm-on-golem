"use client";
import React from "react";
import { createPortal } from "react-dom";
import { cn } from "./cn";

export function Modal({ open, onClose, children, className, labelledBy }: { open: boolean; onClose: () => void; children: React.ReactNode; className?: string; labelledBy?: string }) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const onCloseRef = React.useRef(onClose);
  React.useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCloseRef.current?.(); };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    // focus the container once on open
    setTimeout(() => containerRef.current?.focus(), 0);
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev; };
  }, [open]);

  if (!open) return null;
  const node = (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
      <div className="absolute inset-0 bg-black/40 opacity-100 transition-opacity" onClick={() => onCloseRef.current?.()} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div
          ref={containerRef}
          tabIndex={-1}
          className={cn("w-full max-w-lg origin-top rounded-xl bg-white shadow-lg ring-1 ring-gray-200 transition-transform duration-150 ease-out", className)}
          onClick={(e) => e.stopPropagation()}
        >
          {children}
        </div>
      </div>
    </div>
  );
  // Render to body to avoid sidebar bounds/stacking contexts
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    return createPortal(node, document.body);
  }
  return node;
}
