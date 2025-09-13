"use client";
import React from "react";
import { Spinner } from "./Spinner";

export function StatusBadge({ status }: { status?: string | null }) {
  const s = (status || '').toLowerCase();
  if (s === 'running') return <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">● Running</span>;
  if (s === 'creating') return <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"><Spinner className="h-3.5 w-3.5" /> Creating</span>;
  if (s === 'stopped') return <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">● Stopped</span>;
  if (s === 'terminated' || s === 'deleted') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Terminated</span>;
  if (s === 'error' || s === 'failed') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Error</span>;
  return <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">● Unknown</span>;
}

