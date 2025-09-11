"use client";
import React from "react";
import { cn } from "./cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn("animate-spin text-brand-600", className)} viewBox="0 0 24 24" width="20" height="20" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z" />
    </svg>
  );
}

