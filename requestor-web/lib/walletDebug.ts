"use client";

const PREFIX = "[wallet]";

export function walletDebug(event: string, data?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  console.debug(PREFIX, event, data || {});
}

export function walletWarn(event: string, error: unknown, data?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  console.warn(PREFIX, event, {
    ...(data || {}),
    error: summarizeWalletError(error),
  });
}

export function summarizeWalletError(error: unknown): Record<string, unknown> {
  if (error == null) return { message: "" };
  if (typeof error === "string") return { message: error };
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      cause: summarizeWalletError((error as Error & { cause?: unknown }).cause),
    };
  }
  if (typeof error === "object") {
    const value = error as {
      code?: unknown;
      message?: unknown;
      reason?: unknown;
      shortMessage?: unknown;
      method?: unknown;
    };
    return {
      code: value.code,
      message: value.message,
      reason: value.reason,
      shortMessage: value.shortMessage,
      method: value.method,
    };
  }
  return { message: String(error) };
}
