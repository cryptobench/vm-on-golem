"use client";

type PriceState = Record<string, number>;

const KEY = "requestor_prices_v1";
let timer: ReturnType<typeof setInterval> | null = null;

export function getPriceUSD(symbol: string) {
  if (typeof window === "undefined") return null;
  try {
    const prices = JSON.parse(localStorage.getItem(KEY) || "{}") as PriceState;
    return prices[symbol.toUpperCase()] ?? null;
  } catch {
    return null;
  }
}

export function usdToToken(symbol: string, usd: number) {
  const price = getPriceUSD(symbol);
  return price && price > 0 ? usd / price : null;
}

export function onPricesUpdated(cb: () => void) {
  if (typeof window === "undefined") return () => {};
  const handler = () => cb();
  window.addEventListener("requestor_prices_updated", handler);
  return () => window.removeEventListener("requestor_prices_updated", handler);
}

export function startPricePolling() {
  if (timer || typeof window === "undefined") return () => {};
  const poll = async () => {
    try {
      const response = await fetch(
        "https://api.coingecko.com/api/v3/simple/price?ids=ethereum,golem&vs_currencies=usd",
      );
      if (!response.ok) return;
      const data = await response.json();
      const prices = {
        ETH: Number(data?.ethereum?.usd || 0),
        GLM: Number(data?.golem?.usd || 0),
      };
      localStorage.setItem(KEY, JSON.stringify(prices));
      window.dispatchEvent(new Event("requestor_prices_updated"));
    } catch {
      return;
    }
  };
  poll();
  timer = setInterval(poll, 60_000);
  return () => {
    if (timer) clearInterval(timer);
    timer = null;
  };
}
