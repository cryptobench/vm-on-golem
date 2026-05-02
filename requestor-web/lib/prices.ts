"use client";

type PriceSymbol = "ETH" | "GLM";
type PriceSource = "binance" | "dexscreener" | "coingecko" | "coinpaprika";

type PriceEntry = {
  usd: number;
  source: PriceSource | "legacy";
  updatedAt: number;
};

type PriceState = {
  prices: Partial<Record<PriceSymbol, PriceEntry>>;
  blockedUntil: Partial<Record<PriceSource, number>>;
  lastError?: string;
};

type PriceSnapshot = Record<PriceSymbol, number>;

type RefreshOptions = {
  force?: boolean;
  maxAgeMs?: number;
};

const KEY_V1 = "requestor_prices_v1";
const KEY_V2 = "requestor_prices_v2";
const UPDATE_EVENT = "requestor_prices_updated";

const REFRESH_MS = 5 * 60_000;
const MAX_BACKOFF_MS = 30 * 60_000;
export const PAYMENT_PRICE_MAX_AGE_MS = 10 * 60_000;

const WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2";
const GLM_ADDRESS = "0x7DD9c5Cba05E151C895FDe1CF355C9A1D5DA6429";

let timer: ReturnType<typeof setInterval> | null = null;
let inFlight: Promise<PriceState> | null = null;
const failures: Partial<Record<PriceSource, number>> = {};

class PriceRequestError extends Error {
  constructor(
    message: string,
    readonly source: PriceSource,
    readonly status?: number,
    readonly retryAfterMs?: number,
  ) {
    super(message);
    this.name = "PriceRequestError";
  }
}

function emptyState(): PriceState {
  return { prices: {}, blockedUntil: {} };
}

function isPriceSymbol(symbol: string): symbol is PriceSymbol {
  return symbol === "ETH" || symbol === "GLM";
}

function isPositiveFinite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function readState(): PriceState {
  if (typeof window === "undefined") return emptyState();
  try {
    const raw = localStorage.getItem(KEY_V2);
    if (raw) {
      const parsed = JSON.parse(raw) as PriceState;
      return {
        prices: parsed.prices || {},
        blockedUntil: parsed.blockedUntil || {},
        lastError: parsed.lastError,
      };
    }
  } catch {
    return emptyState();
  }
  return emptyState();
}

function writeState(next: PriceState) {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY_V2, JSON.stringify(next));
}

function dispatchPriceUpdate() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(UPDATE_EVENT));
}

function readLegacyPrice(symbol: PriceSymbol): number | null {
  if (typeof window === "undefined") return null;
  try {
    const prices = JSON.parse(localStorage.getItem(KEY_V1) || "{}") as Record<string, number>;
    const value = prices[symbol];
    return isPositiveFinite(value) ? value : null;
  } catch {
    return null;
  }
}

function snapshotFromState(state: PriceState): PriceSnapshot | null {
  const eth = state.prices.ETH?.usd;
  const glm = state.prices.GLM?.usd;
  if (!isPositiveFinite(eth) || !isPositiveFinite(glm)) return null;
  return { ETH: eth, GLM: glm };
}

function isFresh(state: PriceState, maxAgeMs: number) {
  const now = Date.now();
  return (["ETH", "GLM"] as PriceSymbol[]).every((symbol) => {
    const entry = state.prices[symbol];
    return entry && isPositiveFinite(entry.usd) && now - entry.updatedAt <= maxAgeMs;
  });
}

function parseRetryAfterMs(value: string | null) {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return seconds * 1000;
  const date = Date.parse(value);
  if (Number.isFinite(date)) return Math.max(0, date - Date.now());
  return undefined;
}

async function fetchJson(source: PriceSource, url: string) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    const retryAfterMs = parseRetryAfterMs(response.headers.get("Retry-After"));
    throw new PriceRequestError(
      `${source} returned ${response.status}`,
      source,
      response.status,
      retryAfterMs,
    );
  }
  return response.json();
}

function pickNumber(value: unknown, source: PriceSource, label: string) {
  const price = Number(value);
  if (!isPositiveFinite(price)) {
    throw new PriceRequestError(`${source} returned invalid ${label}`, source);
  }
  return price;
}

async function fetchBinancePrices(): Promise<PriceSnapshot> {
  const source: PriceSource = "binance";
  const symbols = encodeURIComponent(JSON.stringify(["ETHUSDT", "GLMUSDT"]));
  const data = await fetchJson(source, `https://api.binance.com/api/v3/ticker/price?symbols=${symbols}`);
  const rows = Array.isArray(data) ? data : [];
  const bySymbol = new Map(rows.map((row) => [String(row?.symbol), row?.price]));
  return {
    ETH: pickNumber(bySymbol.get("ETHUSDT"), source, "ETH/USD price"),
    GLM: pickNumber(bySymbol.get("GLMUSDT"), source, "GLM/USD price"),
  };
}

async function fetchDexScreenerPrices(): Promise<PriceSnapshot> {
  const source: PriceSource = "dexscreener";
  const data = await fetchJson(
    source,
    `https://api.dexscreener.com/tokens/v1/ethereum/${WETH_ADDRESS},${GLM_ADDRESS}`,
  );
  const rows = Array.isArray(data) ? data : [];
  const findPrice = (symbol: "WETH" | "GLM") => {
    const matches = rows
      .filter((row) => String(row?.baseToken?.symbol).toUpperCase() === symbol)
      .sort((a, b) => Number(b?.liquidity?.usd || 0) - Number(a?.liquidity?.usd || 0));
    return matches[0]?.priceUsd;
  };
  return {
    ETH: pickNumber(findPrice("WETH"), source, "ETH/USD price"),
    GLM: pickNumber(findPrice("GLM"), source, "GLM/USD price"),
  };
}

async function fetchCoinGeckoPrices(): Promise<PriceSnapshot> {
  const source: PriceSource = "coingecko";
  const data = await fetchJson(
    source,
    "https://api.coingecko.com/api/v3/simple/price?ids=ethereum,golem&vs_currencies=usd&include_last_updated_at=true",
  );
  return {
    ETH: pickNumber(data?.ethereum?.usd, source, "ETH/USD price"),
    GLM: pickNumber(data?.golem?.usd, source, "GLM/USD price"),
  };
}

async function fetchCoinPaprikaPrices(): Promise<PriceSnapshot> {
  const source: PriceSource = "coinpaprika";
  const [eth, glm] = await Promise.all([
    fetchJson(source, "https://api.coinpaprika.com/v1/tickers/eth-ethereum"),
    fetchJson(source, "https://api.coinpaprika.com/v1/tickers/glm-golem"),
  ]);
  return {
    ETH: pickNumber(eth?.quotes?.USD?.price, source, "ETH/USD price"),
    GLM: pickNumber(glm?.quotes?.USD?.price, source, "GLM/USD price"),
  };
}

const SOURCES: Array<{ name: PriceSource; fetchPrices: () => Promise<PriceSnapshot> }> = [
  { name: "binance", fetchPrices: fetchBinancePrices },
  { name: "dexscreener", fetchPrices: fetchDexScreenerPrices },
  { name: "coingecko", fetchPrices: fetchCoinGeckoPrices },
  { name: "coinpaprika", fetchPrices: fetchCoinPaprikaPrices },
];

function recordFailure(state: PriceState, error: unknown) {
  const source = error instanceof PriceRequestError ? error.source : undefined;
  const message = error instanceof Error ? error.message : String(error);
  if (!source) return { ...state, lastError: message };

  const nextFailures = (failures[source] || 0) + 1;
  failures[source] = nextFailures;
  const backoffMs =
    error instanceof PriceRequestError && error.retryAfterMs != null
      ? error.retryAfterMs
      : Math.min(MAX_BACKOFF_MS, 30_000 * 2 ** (nextFailures - 1));

  return {
    ...state,
    blockedUntil: {
      ...state.blockedUntil,
      [source]: Date.now() + backoffMs,
    },
    lastError: message,
  };
}

function recordSuccess(state: PriceState, source: PriceSource, prices: PriceSnapshot) {
  failures[source] = 0;
  const updatedAt = Date.now();
  return {
    prices: {
      ETH: { usd: prices.ETH, source, updatedAt },
      GLM: { usd: prices.GLM, source, updatedAt },
    },
    blockedUntil: state.blockedUntil,
  };
}

async function refreshPrices(): Promise<PriceState> {
  let state = readState();
  const now = Date.now();
  const errors: string[] = [];

  for (const source of SOURCES) {
    if ((state.blockedUntil[source.name] || 0) > now) continue;
    try {
      const prices = await source.fetchPrices();
      const next = recordSuccess(state, source.name, prices);
      writeState(next);
      dispatchPriceUpdate();
      return next;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(message);
      state = recordFailure(state, error);
      writeState(state);
    }
  }

  const lastError = errors.length ? errors.join("; ") : state.lastError || "No price sources available";
  const next = { ...state, lastError };
  writeState(next);
  throw new Error(lastError);
}

export function getPriceUSD(symbol: string) {
  if (typeof window === "undefined") return null;
  const normalized = symbol.toUpperCase();
  if (!isPriceSymbol(normalized)) return null;

  const entry = readState().prices[normalized];
  if (entry && isPositiveFinite(entry.usd)) return entry.usd;

  return readLegacyPrice(normalized);
}

export function usdToToken(symbol: string, usd: number) {
  const price = getPriceUSD(symbol);
  return price && price > 0 ? usd / price : null;
}

export async function ensurePricesUSD(options: RefreshOptions = {}) {
  const maxAgeMs = options.maxAgeMs ?? REFRESH_MS;
  const state = readState();
  if (!options.force && isFresh(state, maxAgeMs)) return state;

  if (!inFlight) {
    inFlight = refreshPrices().finally(() => {
      inFlight = null;
    });
  }
  try {
    return await inFlight;
  } catch (error) {
    const fallback = readState();
    if (isFresh(fallback, maxAgeMs)) return fallback;
    throw error;
  }
}

export async function usdToTokenAsync(symbol: string, usd: number, options: RefreshOptions = {}) {
  if (!Number.isFinite(usd) || usd <= 0) return null;
  const normalized = symbol.toUpperCase();
  if (!isPriceSymbol(normalized)) return null;
  const state = await ensurePricesUSD(options);
  const snapshot = snapshotFromState(state);
  const price = snapshot?.[normalized];
  return price && price > 0 ? usd / price : null;
}

export function onPricesUpdated(cb: () => void) {
  if (typeof window === "undefined") return () => {};
  const handler = () => cb();
  window.addEventListener(UPDATE_EVENT, handler);
  return () => window.removeEventListener(UPDATE_EVENT, handler);
}

export function startPricePolling() {
  if (timer || typeof window === "undefined") return () => {};
  const poll = () => {
    ensurePricesUSD({ maxAgeMs: REFRESH_MS }).catch(() => {});
  };
  poll();
  timer = setInterval(poll, REFRESH_MS);
  return () => {
    if (timer) clearInterval(timer);
    timer = null;
  };
}
