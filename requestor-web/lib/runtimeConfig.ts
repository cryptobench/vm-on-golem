"use client";

export type RequestorRuntimeConfig = {
  discoveryApiUrl: string;
  discoveryMode: "arkiv" | "central";
  streamPaymentAddress: string;
  glmTokenAddress: string;
  evmChainId: string;
  evmChainName: string;
  evmRpcUrl: string;
  evmExplorerUrl: string;
  golemEnvironment: string;
  arkivDevRpcUrl: string;
  arkivDevWsUrl: string;
};

declare global {
  interface Window {
    __GOLEM_REQUESTOR_RUNTIME_CONFIG__?: Partial<RequestorRuntimeConfig>;
  }
}

const DEFAULTS: RequestorRuntimeConfig = {
  discoveryApiUrl: "http://195.201.39.101:9001/api/v1",
  discoveryMode: "central",
  streamPaymentAddress: "",
  glmTokenAddress: "",
  evmChainId: "0x88bb0",
  evmChainName: "Ethereum Hoodi",
  evmRpcUrl: "https://ethereum-hoodi-rpc.publicnode.com",
  evmExplorerUrl: "https://hoodi.etherscan.io",
  golemEnvironment: "",
  arkivDevRpcUrl: "",
  arkivDevWsUrl: "",
};

function envValue(name: keyof PublicRuntimeEnv): string {
  return publicRuntimeEnv()[name] || "";
}

type PublicRuntimeEnv = {
  NEXT_PUBLIC_DISCOVERY_API_URL?: string;
  NEXT_PUBLIC_DISCOVERY_MODE?: string;
  NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS?: string;
  NEXT_PUBLIC_GLM_TOKEN_ADDRESS?: string;
  NEXT_PUBLIC_EVM_CHAIN_ID?: string;
  NEXT_PUBLIC_EVM_CHAIN_NAME?: string;
  NEXT_PUBLIC_EVM_RPC_URL?: string;
  NEXT_PUBLIC_EVM_EXPLORER_URL?: string;
  NEXT_PUBLIC_GOLEM_ENVIRONMENT?: string;
  NEXT_PUBLIC_ARKIV_DEV_RPC_URL?: string;
  NEXT_PUBLIC_ARKIV_DEV_WS_URL?: string;
};

function publicRuntimeEnv(): PublicRuntimeEnv {
  return {
    NEXT_PUBLIC_DISCOVERY_API_URL: process.env.NEXT_PUBLIC_DISCOVERY_API_URL,
    NEXT_PUBLIC_DISCOVERY_MODE: process.env.NEXT_PUBLIC_DISCOVERY_MODE,
    NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS:
      process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS,
    NEXT_PUBLIC_GLM_TOKEN_ADDRESS: process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS,
    NEXT_PUBLIC_EVM_CHAIN_ID: process.env.NEXT_PUBLIC_EVM_CHAIN_ID,
    NEXT_PUBLIC_EVM_CHAIN_NAME: process.env.NEXT_PUBLIC_EVM_CHAIN_NAME,
    NEXT_PUBLIC_EVM_RPC_URL: process.env.NEXT_PUBLIC_EVM_RPC_URL,
    NEXT_PUBLIC_EVM_EXPLORER_URL: process.env.NEXT_PUBLIC_EVM_EXPLORER_URL,
    NEXT_PUBLIC_GOLEM_ENVIRONMENT: process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT,
    NEXT_PUBLIC_ARKIV_DEV_RPC_URL: process.env.NEXT_PUBLIC_ARKIV_DEV_RPC_URL,
    NEXT_PUBLIC_ARKIV_DEV_WS_URL: process.env.NEXT_PUBLIC_ARKIV_DEV_WS_URL,
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
    discoveryApiUrl: envValue("NEXT_PUBLIC_DISCOVERY_API_URL"),
    discoveryMode:
      envValue("NEXT_PUBLIC_DISCOVERY_MODE").toLowerCase() === "arkiv"
        ? "arkiv"
        : undefined,
    streamPaymentAddress: envValue("NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS"),
    glmTokenAddress: envValue("NEXT_PUBLIC_GLM_TOKEN_ADDRESS"),
    evmChainId: envValue("NEXT_PUBLIC_EVM_CHAIN_ID"),
    evmChainName: envValue("NEXT_PUBLIC_EVM_CHAIN_NAME"),
    evmRpcUrl: envValue("NEXT_PUBLIC_EVM_RPC_URL"),
    evmExplorerUrl: envValue("NEXT_PUBLIC_EVM_EXPLORER_URL"),
    golemEnvironment: envValue("NEXT_PUBLIC_GOLEM_ENVIRONMENT"),
    arkivDevRpcUrl: envValue("NEXT_PUBLIC_ARKIV_DEV_RPC_URL"),
    arkivDevWsUrl: envValue("NEXT_PUBLIC_ARKIV_DEV_WS_URL"),
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
