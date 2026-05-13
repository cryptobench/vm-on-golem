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
  RiShutDownLine,
  RiStackLine,
  RiWebhookLine,
} from "@remixicon/react";
import { Button, SidebarLayout, StatusBadge, cn } from "@golem/ui";
import type { DashboardData } from "../lib/useProviderData";
import type { ProviderServiceStatus } from "../lib/types";
import { shortAddress } from "../lib/format";
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
  serviceStatus,
  busyAction,
  children,
  onNavigate,
  onStopProvider,
}: {
  activePage: PageId | "vm-detail";
  data: DashboardData | null;
  serviceStatus: ProviderServiceStatus | null;
  busyAction: "start" | "stop" | null;
  children: React.ReactNode;
  onNavigate: (target: NavigateTarget) => void;
  onStopProvider: () => void;
}) {
  const info = data?.info;

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
            <div className="flex items-center justify-between gap-3">
              <StatusBadge
                tone={serviceStatus?.running ? "success" : "neutral"}
                label={`Service: ${serviceStatus?.running ? "Running" : "Stopped"}`}
              />
              <Button
                variant="secondary"
                busy={busyAction === "stop"}
                disabled={!serviceStatus?.running || busyAction !== null}
                onClick={onStopProvider}
                title="Stop provider"
                aria-label="Stop provider"
                className="h-8 w-8 px-0"
              >
                <RiShutDownLine className="h-4 w-4" aria-hidden />
              </Button>
            </div>
            <div className="mt-5">v0.9.4</div>
            <div className="mt-4 text-xs font-medium uppercase text-text-muted">
              Provider ID
            </div>
            <button
              type="button"
              className="mt-1 inline-flex items-center gap-2 font-mono text-sm text-text-primary"
              onClick={() => {
                if (info?.provider_id) void navigator.clipboard.writeText(info.provider_id);
              }}
            >
              {shortAddress(info?.provider_id)}
              <RiFileCopyLine className="h-4 w-4 text-text-muted" aria-hidden />
            </button>
            <div className="mt-4 flex items-center gap-2 text-text-primary">
              <span className="font-medium">{info?.country ?? "--"}</span>
              <span className="text-border-strong">|</span>
              <span>{info?.country === "SE" ? "Sweden" : info?.country ?? "--"}</span>
            </div>
            <div className="mt-4">
              <span className="text-text-muted">IP</span>{" "}
              <span className="font-mono text-text-primary">
                {info?.ip_address ?? "--"}
              </span>
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
