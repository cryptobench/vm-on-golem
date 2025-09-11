"use client";
import React from "react";

export type AdsMode = 'golem-base' | 'central';
export type AdsConfig = {
  mode: AdsMode;
  discovery_url: string; // used when mode === 'central'
  golem_base_rpc_url: string; // used when mode === 'golem-base'
  golem_base_ws_url: string; // used when mode === 'golem-base'
  chain_id: number; // numeric chain id for Golem Base
  advertisement_interval_seconds?: number; // optional for created_at estimation
};

const DEFAULTS: AdsConfig = {
  mode: 'golem-base',
  discovery_url: process.env.NEXT_PUBLIC_DISCOVERY_API_URL || 'http://195.201.39.101:9001/api/v1',
  // Defaults aligned with requestor config
  golem_base_rpc_url: 'https://ethwarsaw.holesky.golemdb.io/rpc',
  golem_base_ws_url: 'wss://ethwarsaw.holesky.golemdb.io/rpc/ws',
  chain_id: (() => {
    const hex = (process.env.NEXT_PUBLIC_EVM_CHAIN_ID || '0x4268').toString();
    try { return parseInt(hex, 16); } catch { return 17000; }
  })(),
  advertisement_interval_seconds: 240,
};

// Profiles support: allow multiple saved advertisement server configs
export type AdsProfile = { id: string; name: string; config: AdsConfig };
const PROFILES_KEY = 'requestor_ads_profiles_v1';
const ACTIVE_KEY = 'requestor_ads_active_profile_v1';

function uuid() { return Math.random().toString(36).slice(2, 10); }

function loadProfiles(): { profiles: AdsProfile[]; activeId: string } {
  if (typeof window === 'undefined') return { profiles: [{ id: 'default', name: 'Default', config: DEFAULTS }], activeId: 'default' };
  try {
    const stored = JSON.parse(localStorage.getItem(PROFILES_KEY) || '[]');
    let profiles: AdsProfile[] = Array.isArray(stored) ? stored : [];
    // Migrate from legacy single-config storage
    const legacy = JSON.parse(localStorage.getItem('requestor_ads_config_v1') || 'null');
    if (!profiles.length && legacy && typeof legacy === 'object') {
      profiles = [{ id: 'default', name: 'Default', config: { ...DEFAULTS, ...legacy } }];
    }
    if (!profiles.length) profiles = [{ id: 'default', name: 'Default', config: DEFAULTS }];
    const activeId = String(localStorage.getItem(ACTIVE_KEY) || profiles[0].id);
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
