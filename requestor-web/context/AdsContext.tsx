"use client";

import React from "react";
import { getRequestorRuntimeConfig } from "../lib/runtimeConfig";

export type AdsConfig = {
  discovery_ws_url: string;
};

const STORAGE_KEY = "requestor_discovery_config_v1";

function defaultAdsConfig(): AdsConfig {
  return {
    discovery_ws_url: getRequestorRuntimeConfig().discoveryWsUrl,
  };
}

function loadAdsConfig(): AdsConfig {
  const defaults = defaultAdsConfig();
  if (typeof window === "undefined") return defaults;
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (!stored || typeof stored !== "object") return defaults;
    return {
      discovery_ws_url:
        typeof stored.discovery_ws_url === "string" &&
        stored.discovery_ws_url.trim()
          ? stored.discovery_ws_url
          : defaults.discovery_ws_url,
    };
  } catch {
    return defaults;
  }
}

function saveAdsConfig(config: AdsConfig): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export const AdsContext = React.createContext<{
  ads: AdsConfig;
  setAds: (next: AdsConfig) => void;
}>({
  ads: defaultAdsConfig(),
  setAds: () => {},
});

export function AdsProvider({ children }: { children: React.ReactNode }) {
  const [ads, setAdsState] = React.useState<AdsConfig>(() => loadAdsConfig());

  const setAds = (next: AdsConfig) => {
    const normalized = {
      discovery_ws_url: next.discovery_ws_url.trim(),
    };
    setAdsState(normalized);
    saveAdsConfig(normalized);
  };

  return (
    <AdsContext.Provider value={{ ads, setAds }}>
      {children}
    </AdsContext.Provider>
  );
}

export function useAds() {
  return React.useContext(AdsContext);
}
