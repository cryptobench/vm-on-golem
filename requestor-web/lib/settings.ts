"use client";

import { getRequestorRuntimeConfig } from "./runtimeConfig";

export type SSHKey = {
  id: string;
  name: string;
  value: string;
  public_key?: string;
};

export type Settings = {
  ssh_public_key?: string;
  ssh_keys?: SSHKey[];
  default_ssh_key_id?: string;
  stream_payment_address?: string;
  glm_token_address?: string;
  evm_chain_id?: string;
  evm_chain_name?: string;
  evm_rpc_url?: string;
  evm_ws_url?: string;
  evm_explorer_url?: string;
  display_currency?: "fiat" | "token";
  show_terminated?: boolean;
  show_ended_streams?: boolean;
};

const SETTINGS_KEY = "requestor_settings_v1";
const STALE_STREAM_PAYMENT_ADDRESSES = new Set([
  "0x0281b792b5491e3548c8fc17c24a2e0cb99fbec2",
]);

export function loadSettings(): Settings {
  if (typeof window === "undefined") return {};
  try {
    const settings = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
    const defaultStreamPayment =
      getRequestorRuntimeConfig().streamPaymentAddress || "";
    const currentStreamPayment = String(
      settings.stream_payment_address || "",
    ).toLowerCase();
    if (
      defaultStreamPayment &&
      STALE_STREAM_PAYMENT_ADDRESSES.has(currentStreamPayment)
    ) {
      const migrated = {
        ...settings,
        stream_payment_address: defaultStreamPayment,
      };
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(migrated));
      return migrated;
    }
    return settings;
  } catch {
    return {};
  }
}

export function saveSettings(next: Partial<Settings>) {
  if (typeof window === "undefined") return;
  const settings = { ...loadSettings(), ...next };
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  window.dispatchEvent(
    new CustomEvent("requestor_settings_changed", { detail: settings }),
  );
}
