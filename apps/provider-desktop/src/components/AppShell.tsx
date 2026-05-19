import {
  RiAlertLine,
  RiBarChartBoxLine,
  RiCheckboxCircleLine,
  RiFileCopyLine,
  RiHeartPulseLine,
  RiHome5Line,
  RiLineChartLine,
  RiNodeTree,
  RiSettings3Line,
  RiStackLine,
  RiWebhookLine,
} from "@remixicon/react";
import { getVersion } from "@tauri-apps/api/app";
import { useEffect, useState } from "react";
import { Button, SidebarLayout, cn } from "@golem/ui";
import type { DashboardData } from "../lib/useProviderData";
import { EMPTY_VALUE } from "../lib/format";
import type { NavigateTarget, PageId } from "./types";

const NAV: Array<{ id: PageId; label: string; icon: typeof RiHome5Line }> = [
  { id: "overview", label: "Overview", icon: RiHome5Line },
  { id: "vms", label: "Virtual Machines", icon: RiStackLine },
  { id: "streams", label: "Streams & Earnings", icon: RiLineChartLine },
  { id: "monitoring", label: "Monitoring", icon: RiBarChartBoxLine },
  { id: "alerts", label: "Alerts", icon: RiAlertLine },
  { id: "webhooks", label: "Webhooks", icon: RiWebhookLine },
  { id: "settings", label: "Settings", icon: RiSettings3Line },
  { id: "health", label: "Health", icon: RiHeartPulseLine },
];

export function AppShell({
  activePage,
  data,
  children,
  onNavigate,
}: {
  activePage: PageId | "vm-detail";
  data: DashboardData | null;
  children: React.ReactNode;
  onNavigate: (target: NavigateTarget) => void;
}) {
  const info = data?.info;
  const providerId = info?.provider_id ?? "";
  const [appVersion, setAppVersion] = useState<string>(EMPTY_VALUE);
  const [copiedProviderId, setCopiedProviderId] = useState(false);

  useEffect(() => {
    let mounted = true;
    getVersion()
      .then((version) => {
        if (mounted) setAppVersion(version);
      })
      .catch(() => {
        if (mounted) setAppVersion(EMPTY_VALUE);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!copiedProviderId) return undefined;
    const timeout = window.setTimeout(() => setCopiedProviderId(false), 1600);
    return () => window.clearTimeout(timeout);
  }, [copiedProviderId]);

  async function copyProviderId() {
    if (!providerId) return;
    try {
      await copyText(providerId);
      setCopiedProviderId(true);
    } catch {
      setCopiedProviderId(false);
    }
  }

  return (
    <SidebarLayout
      sidebar={
        <div className="flex h-screen flex-col">
          <div className="flex items-center gap-3 px-8 py-8">
            <RiNodeTree className="h-9 w-9 text-primary" aria-hidden />
            <div className="text-xl font-semibold text-text-primary">
              Golem Provider
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-4">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active =
                activePage === item.id ||
                (activePage === "vm-detail" && item.id === "vms");
              return (
                <button
                  key={item.id}
                  type="button"
                  className={cn(
                    "flex h-12 w-full items-center gap-3 rounded-lg px-4 text-left text-sm font-medium transition",
                    active
                      ? "bg-primary-soft text-primary"
                      : "text-text-secondary hover:bg-surface-muted hover:text-text-primary",
                  )}
                  onClick={() => onNavigate({ page: item.id })}
                >
                  <Icon className="h-5 w-5" aria-hidden />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </nav>

          <div className="border-t border-border px-6 py-5 text-sm text-text-secondary">
            <div>
              {appVersion === EMPTY_VALUE ? EMPTY_VALUE : `v${appVersion}`}
            </div>
            <div className="mt-4 text-xs font-medium uppercase text-text-muted">
              Provider ID
            </div>
            <div className="mt-2 flex items-start gap-2">
              <div className="min-w-0 flex-1 break-all font-mono text-sm leading-5 text-text-primary">
                {providerId || EMPTY_VALUE}
              </div>
              <Button
                variant="secondary"
                className="h-8 w-8 shrink-0 px-0"
                disabled={!providerId}
                onClick={() => void copyProviderId()}
                title={copiedProviderId ? "Copied provider ID" : "Copy provider ID"}
                aria-label={copiedProviderId ? "Copied provider ID" : "Copy provider ID"}
              >
                {copiedProviderId ? (
                  <RiCheckboxCircleLine className="h-4 w-4" aria-hidden />
                ) : (
                  <RiFileCopyLine className="h-4 w-4" aria-hidden />
                )}
              </Button>
            </div>
          </div>
        </div>
      }
    >
      <div className="min-h-screen px-8 py-8">
        {children}
      </div>
    </SidebarLayout>
  );
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Fall through for WebViews where clipboard permissions are unavailable.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }
}
