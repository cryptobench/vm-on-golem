"use client";
import React from "react";
import { loadSettings, saveSettings, type Settings } from "../lib/api";

export function useSettings() {
  const [settings, setSettings] = React.useState<Settings>(() => loadSettings());

  React.useEffect(() => {
    const onCustom = (e: any) => {
      try { setSettings(e.detail as Settings); } catch {}
    };
    const onStorage = () => {
      try { setSettings(loadSettings()); } catch {}
    };
    if (typeof window !== 'undefined') {
      window.addEventListener('requestor_settings_changed', onCustom as any);
      window.addEventListener('storage', onStorage);
      return () => {
        window.removeEventListener('requestor_settings_changed', onCustom as any);
        window.removeEventListener('storage', onStorage);
      };
    }
  }, []);

  const update = React.useCallback((next: Partial<Settings>) => {
    saveSettings(next);
    setSettings(loadSettings());
  }, []);

  const displayCurrency: 'fiat' | 'token' = settings.display_currency === 'token' ? 'token' : 'fiat';
  const setDisplayCurrency = React.useCallback((v: 'fiat' | 'token') => update({ display_currency: v }), [update]);

  return { settings, setSettings: update, displayCurrency, setDisplayCurrency };
}

