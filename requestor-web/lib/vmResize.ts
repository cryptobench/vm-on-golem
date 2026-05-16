"use client";

import type { VMResources } from "./api";

export type ResizeLimits = {
  cpu: number;
  memory: number;
  storage: number;
};

export function computeResizeLimits(
  current: VMResources,
  summary?: {
    resources?: {
      available?: unknown;
      total?: unknown;
    };
  } | null,
): ResizeLimits {
  const available = readResourceBucket(summary?.resources?.available);
  const total = readResourceBucket(summary?.resources?.total);

  return {
    cpu: maxFor("cpu", current.cpu, available, total),
    memory: maxFor("memory", current.memory, available, total),
    storage: maxFor("storage", current.storage, available, total),
  };
}

export function clampResizeResources(
  next: VMResources,
  current: VMResources,
  limits: ResizeLimits,
): VMResources {
  return {
    cpu: clampInteger(next.cpu, 1, limits.cpu),
    memory: clampInteger(next.memory, 1, limits.memory),
    storage: clampInteger(next.storage, current.storage, limits.storage),
  };
}

function maxFor(
  key: keyof VMResources,
  current: number,
  available: Partial<ResizeLimits>,
  total: Partial<ResizeLimits>,
) {
  const fromAvailable = current + positiveInteger(available[key], 0);
  const fromTotal = positiveInteger(total[key], 0);
  const providerMax =
    fromTotal > 0 ? Math.min(fromAvailable, fromTotal) : fromAvailable;
  return Math.max(current, providerMax);
}

function readResourceBucket(value: unknown): Partial<ResizeLimits> {
  const source = (value || {}) as Record<string, unknown>;
  return {
    cpu: positiveInteger(source.cpu, 0),
    memory: positiveInteger(source.memory, 0),
    storage: positiveInteger(source.storage, 0),
  };
}

function clampInteger(value: number, min: number, max: number) {
  const safeMin = Math.max(1, Math.floor(min));
  const safeMax = Math.max(safeMin, Math.floor(max));
  const safeValue = Number.isFinite(value) ? Math.floor(value) : safeMin;
  return Math.min(Math.max(safeValue, safeMin), safeMax);
}

function positiveInteger(value: unknown, fallback: number) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return fallback;
  return Math.floor(numeric);
}
