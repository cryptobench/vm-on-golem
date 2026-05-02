"use client";
import React from "react";

export type AdsMode = 'arkiv' | 'central';
export type AdsConfig = {
  mode: AdsMode;
  discovery_url: string; // used when mode === 'central'
  arkiv_rpc_url: string;
  arkiv_ws_url: string;
  chain_id: number; // numeric chain id for Arkiv payments/network metadata
  advertisement_interval_seconds?: number; // optional for created_at estimation
};

type StoredAdsConfig = Partial<AdsConfig>;

const BASE_RPC_URL = 'https://kaolin.hoodi.arkiv.network/rpc';
const BASE_WS_URL = 'wss://kaolin.hoodi.arkiv.network/rpc/ws';
const DEFAULTS: AdsConfig = (() => {
  const isDevEnv = (process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT || '').toLowerCase() === 'development';
  // Allow explicit dev overrides when GOLEM_ENVIRONMENT=development
  const devRpc = process.env.NEXT_PUBLIC_ARKIV_DEV_RPC_URL || '';
  const devWs = process.env.NEXT_PUBLIC_ARKIV_DEV_WS_URL || '';
  const baseRpc = isDevEnv && devRpc ? devRpc : BASE_RPC_URL;
  const baseWs = isDevEnv && devWs ? devWs : BASE_WS_URL;
  return {
    mode: 'arkiv',
    discovery_url: process.env.NEXT_PUBLIC_DISCOVERY_API_URL || 'http://195.201.39.101:9001/api/v1',
    arkiv_rpc_url: baseRpc,
    arkiv_ws_url: baseWs,
    chain_id: (() => {
      // Keep existing default for backward compat; payments chain handled separately in UI
      const def = process.env.NEXT_PUBLIC_EVM_CHAIN_ID || '0x6013a';
      try { return parseInt(def, 16); } catch { return 393530; }
    })(),
    advertisement_interval_seconds: 240,
  };
})();

// Profiles support: allow multiple saved advertisement server configs
export type AdsProfile = { id: string; name: string; config: AdsConfig };
const PROFILES_KEY = 'requestor_ads_profiles_v1';
const ACTIVE_KEY = 'requestor_ads_active_profile_v1';

function uuid() { return Math.random().toString(36).slice(2, 10); }

function normalizeAdsConfig(config: StoredAdsConfig): AdsConfig {
  const next = { ...DEFAULTS, ...config };
  next.mode = next.mode === 'central' ? 'central' : 'arkiv';
  next.arkiv_rpc_url = config.arkiv_rpc_url || DEFAULTS.arkiv_rpc_url;
  next.arkiv_ws_url = config.arkiv_ws_url || DEFAULTS.arkiv_ws_url;
  return next;
}

function loadProfiles(): { profiles: AdsProfile[]; activeId: string } {
  if (typeof window === 'undefined') return { profiles: [{ id: 'default', name: 'Default', config: DEFAULTS }], activeId: 'default' };
  try {
    const stored = JSON.parse(localStorage.getItem(PROFILES_KEY) || '[]');
    let profiles: AdsProfile[] = Array.isArray(stored)
      ? stored.map((profile) => ({
          ...profile,
          config: normalizeAdsConfig(profile.config || {}),
        }))
      : [];
    let shouldPersistProfiles = profiles.length > 0;
    // Migrate from legacy single-config storage
    const legacy = JSON.parse(localStorage.getItem('requestor_ads_config_v1') || 'null');
    if (!profiles.length && legacy && typeof legacy === 'object') {
      profiles = [{ id: 'default', name: 'Default', config: normalizeAdsConfig(legacy) }];
      shouldPersistProfiles = true;
    }
    if (!profiles.length) {
      profiles = [{ id: 'default', name: 'Default', config: DEFAULTS }];
      shouldPersistProfiles = true;
    }

    if (shouldPersistProfiles) {
      localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
    }
    const activeId = String(localStorage.getItem(ACTIVE_KEY) || profiles[0].id);
    if (shouldPersistProfiles) {
      localStorage.setItem(ACTIVE_KEY, activeId);
    }
    return { profiles, activeId };
  } catch {
    return { profiles: [{ id: 'default', name: 'Default', config: DEFAULTS }], activeId: 'default' };
  }
}

function saveProfiles(profiles: AdsProfile[], activeId: string) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
  localStorage.setItem(ACTIVE_KEY, activeId);
}

export const AdsContext = React.createContext<{
  ads: AdsConfig;
  setAds: (next: AdsConfig) => void;
  profiles: AdsProfile[];
  activeId: string;
  setActive: (id: string) => void;
  addProfile: (name: string, config?: AdsConfig) => void;
  removeProfile: (id: string) => void;
  renameProfile: (id: string, name: string) => void;
}>({ ads: DEFAULTS, setAds: () => {}, profiles: [{ id: 'default', name: 'Default', config: DEFAULTS }], activeId: 'default', setActive: () => {}, addProfile: () => {}, removeProfile: () => {}, renameProfile: () => {} });

export function AdsProvider({ children }: { children: React.ReactNode }) {
  const [{ profiles, activeId }, setState] = React.useState<{ profiles: AdsProfile[]; activeId: string }>(() => loadProfiles());
  const ads = React.useMemo(() => profiles.find(p => p.id === activeId)?.config || profiles[0]?.config || DEFAULTS, [profiles, activeId]);

  const persist = (nextProfiles: AdsProfile[], nextActive: string) => { setState({ profiles: nextProfiles, activeId: nextActive }); saveProfiles(nextProfiles, nextActive); };

  const setAds = (next: AdsConfig) => {
    const idx = profiles.findIndex(p => p.id === activeId);
    if (idx >= 0) {
      const copy = profiles.slice();
      copy[idx] = { ...copy[idx], config: next };
      persist(copy, activeId);
    }
  };
  const setActive = (id: string) => { if (profiles.some(p => p.id === id)) persist(profiles, id); };
  const addProfile = (name: string, config?: AdsConfig) => { const p: AdsProfile = { id: uuid(), name: name || 'Profile', config: config || ads }; persist([...profiles, p], p.id); };
  const removeProfile = (id: string) => {
    if (profiles.length <= 1) return; // keep at least one
    const filtered = profiles.filter(p => p.id !== id);
    const nextActive = activeId === id ? filtered[0].id : activeId;
    persist(filtered, nextActive);
  };
  const renameProfile = (id: string, name: string) => { const i = profiles.findIndex(p => p.id === id); if (i >= 0) { const copy = profiles.slice(); copy[i] = { ...copy[i], name }; persist(copy, activeId); } };

  return (
    <AdsContext.Provider value={{ ads, setAds, profiles, activeId, setActive, addProfile, removeProfile, renameProfile }}>{children}</AdsContext.Provider>
  );
}

export function useAds() { return React.useContext(AdsContext); }
