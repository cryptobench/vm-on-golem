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
      action?: unknown;
      data?: unknown;
      transaction?: { to?: unknown; from?: unknown; data?: unknown; value?: unknown };
      receipt?: {
        status?: unknown;
        hash?: unknown;
        to?: unknown;
        from?: unknown;
        gasUsed?: unknown;
        blockNumber?: unknown;
      };
    };
    return {
      code: value.code,
      message: value.message,
      reason: value.reason,
      shortMessage: value.shortMessage,
      method: value.method,
      action: value.action,
      data: truncate(value.data),
      transaction: value.transaction
        ? {
            to: value.transaction.to,
            from: value.transaction.from,
            dataLength: String(value.transaction.data || "").length,
            dataPrefix: truncate(value.transaction.data, 18),
            value: stringifyBigInt(value.transaction.value),
          }
        : undefined,
      receipt: value.receipt
        ? {
            status: value.receipt.status,
            hash: value.receipt.hash,
            to: value.receipt.to,
            from: value.receipt.from,
            gasUsed: stringifyBigInt(value.receipt.gasUsed),
            blockNumber: value.receipt.blockNumber,
          }
        : undefined,
    };
  }
  return { message: String(error) };
}

function truncate(value: unknown, maxLength = 180) {
  if (value == null) return value;
  const text = String(value);
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function stringifyBigInt(value: unknown) {
  return typeof value === "bigint" ? String(value) : value;
}
