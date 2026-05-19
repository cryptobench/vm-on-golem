"use client";

export type RequestorRuntimeConfig = {
  discoveryWsUrl: string;
  streamPaymentAddress: string;
  glmTokenAddress: string;
  evmChainId: string;
  evmChainName: string;
  evmRpcUrl: string;
  evmWsUrl: string;
  evmExplorerUrl: string;
  golemEnvironment: string;
};

declare global {
  interface Window {
    __GOLEM_REQUESTOR_RUNTIME_CONFIG__?: Partial<RequestorRuntimeConfig>;
  }
}

const DEFAULTS: RequestorRuntimeConfig = {
  discoveryWsUrl: "wss://78.46.172.104/api/v1/discovery/requestors",
  streamPaymentAddress: "0x479044F8A58276DC15d0d924a6A92Ec663877D00",
  glmTokenAddress: "0x55555555555556AcFf9C332Ed151758858bd7a26",
  evmChainId: "0x88bb0",
  evmChainName: "Ethereum Hoodi",
  evmRpcUrl: "https://rpc.hoodi.ethpandaops.io",
  evmWsUrl: "wss://ethereum-hoodi-rpc.publicnode.com",
  evmExplorerUrl: "https://hoodi.etherscan.io",
  golemEnvironment: "",
};

function envValue(name: keyof PublicRuntimeEnv): string {
  return publicRuntimeEnv()[name] || "";
}

type PublicRuntimeEnv = {
  NEXT_PUBLIC_DISCOVERY_WS_URL?: string;
  NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS?: string;
  NEXT_PUBLIC_GLM_TOKEN_ADDRESS?: string;
  NEXT_PUBLIC_EVM_CHAIN_ID?: string;
  NEXT_PUBLIC_EVM_CHAIN_NAME?: string;
  NEXT_PUBLIC_EVM_RPC_URL?: string;
  NEXT_PUBLIC_EVM_WS_URL?: string;
  NEXT_PUBLIC_EVM_EXPLORER_URL?: string;
  NEXT_PUBLIC_GOLEM_ENVIRONMENT?: string;
};

function publicRuntimeEnv(): PublicRuntimeEnv {
  return {
    NEXT_PUBLIC_DISCOVERY_WS_URL: process.env.NEXT_PUBLIC_DISCOVERY_WS_URL,
    NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS:
      process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS,
    NEXT_PUBLIC_GLM_TOKEN_ADDRESS: process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS,
    NEXT_PUBLIC_EVM_CHAIN_ID: process.env.NEXT_PUBLIC_EVM_CHAIN_ID,
    NEXT_PUBLIC_EVM_CHAIN_NAME: process.env.NEXT_PUBLIC_EVM_CHAIN_NAME,
    NEXT_PUBLIC_EVM_RPC_URL: process.env.NEXT_PUBLIC_EVM_RPC_URL,
    NEXT_PUBLIC_EVM_WS_URL: process.env.NEXT_PUBLIC_EVM_WS_URL,
    NEXT_PUBLIC_EVM_EXPLORER_URL: process.env.NEXT_PUBLIC_EVM_EXPLORER_URL,
    NEXT_PUBLIC_GOLEM_ENVIRONMENT: process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT,
  };
}

export function setRequestorRuntimeConfig(
  overrides: Partial<RequestorRuntimeConfig>,
): void {
  if (typeof window === "undefined") return;
  window.__GOLEM_REQUESTOR_RUNTIME_CONFIG__ = {
    ...(window.__GOLEM_REQUESTOR_RUNTIME_CONFIG__ || {}),
    ...overrides,
  };
}

export function getRequestorRuntimeConfig(): RequestorRuntimeConfig {
  const runtime =
    typeof window === "undefined"
      ? {}
      : window.__GOLEM_REQUESTOR_RUNTIME_CONFIG__ || {};
  const env: Partial<RequestorRuntimeConfig> = {
    discoveryWsUrl: envValue("NEXT_PUBLIC_DISCOVERY_WS_URL"),
    streamPaymentAddress: envValue("NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS"),
    glmTokenAddress: envValue("NEXT_PUBLIC_GLM_TOKEN_ADDRESS"),
    evmChainId: envValue("NEXT_PUBLIC_EVM_CHAIN_ID"),
    evmChainName: envValue("NEXT_PUBLIC_EVM_CHAIN_NAME"),
    evmRpcUrl: envValue("NEXT_PUBLIC_EVM_RPC_URL"),
    evmWsUrl: envValue("NEXT_PUBLIC_EVM_WS_URL"),
    evmExplorerUrl: envValue("NEXT_PUBLIC_EVM_EXPLORER_URL"),
    golemEnvironment: envValue("NEXT_PUBLIC_GOLEM_ENVIRONMENT"),
  };
  return { ...DEFAULTS, ...compact(env), ...compact(runtime) };
}

function compact<T extends Record<string, unknown>>(value: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(value).filter(
      ([, entry]) => entry !== undefined && entry !== "",
    ),
  ) as Partial<T>;
}
