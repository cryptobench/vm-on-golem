import type React from "react";
import {
  RiCpuLine,
  RiDatabase2Line,
  RiHardDrive3Line,
} from "@remixicon/react";
import type {
  ProviderPricingSettings,
  UpdateProviderPricing,
  VMResources,
} from "../../lib/types";

export type SettingsTab = "resources" | "pricing" | "calculator";
export type ResourceKey = keyof VMResources;
export type PricingKey = keyof UpdateProviderPricing;

export type ResourceField = {
  key: ResourceKey;
  label: string;
  description: string;
  unit: string;
  icon: React.ReactNode;
};

export type PricingField = {
  key: PricingKey;
  glmKey: keyof Pick<
    ProviderPricingSettings,
    | "glm_per_core_month"
    | "glm_per_gb_ram_month"
    | "glm_per_gb_storage_month"
  >;
  label: string;
  description: string;
  unit: string;
  icon: React.ReactNode;
};

export const SETTINGS_TABS = [
  { id: "resources", label: "Resources" },
  { id: "pricing", label: "Pricing" },
  { id: "calculator", label: "Earnings Calculator" },
] satisfies Array<{ id: SettingsTab; label: string }>;

export const RESOURCE_FIELDS: ResourceField[] = [
  {
    key: "cpu",
    label: "CPU Cores",
    description: "Number of CPU cores available for virtual machines.",
    unit: "cores",
    icon: <RiCpuLine className="h-5 w-5" />,
  },
  {
    key: "memory",
    label: "Memory (RAM)",
    description: "Amount of RAM available for virtual machines.",
    unit: "GB",
    icon: <RiDatabase2Line className="h-5 w-5" />,
  },
  {
    key: "storage",
    label: "Storage",
    description: "Disk space available for virtual machines.",
    unit: "GB",
    icon: <RiHardDrive3Line className="h-5 w-5" />,
  },
];

export const PRICING_FIELDS: PricingField[] = [
  {
    key: "usd_per_core_month",
    glmKey: "glm_per_core_month",
    label: "CPU Price",
    description: "Set the price per CPU core per month.",
    unit: "per core / month",
    icon: <RiCpuLine className="h-5 w-5" />,
  },
  {
    key: "usd_per_gb_ram_month",
    glmKey: "glm_per_gb_ram_month",
    label: "Memory Price",
    description: "Set the price per GB of RAM per month.",
    unit: "per GB / month",
    icon: <RiDatabase2Line className="h-5 w-5" />,
  },
  {
    key: "usd_per_gb_storage_month",
    glmKey: "glm_per_gb_storage_month",
    label: "Storage Price",
    description: "Set the price per GB of storage per month.",
    unit: "per GB / month",
    icon: <RiHardDrive3Line className="h-5 w-5" />,
  },
];
