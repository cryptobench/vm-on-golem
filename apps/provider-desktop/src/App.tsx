import React from "react";
import { Card, CardBody, PageHeader } from "@golem/ui";
import { startPricePolling } from "@golem/prices";
import { AppShell } from "./components/AppShell";
import { ServiceStopped } from "./components/StateViews";
import type { NavigateTarget, PageId } from "./components/types";
import { AlertsPage } from "./features/alerts/AlertsPage";
import { MonitoringPage } from "./features/monitoring/MonitoringPage";
import { OverviewPage } from "./features/overview/OverviewPage";
import { StreamsPage } from "./features/streams/StreamsPage";
import { VirtualMachinesPage } from "./features/vms/VirtualMachinesPage";
import { VmDetailsPage } from "./features/vm-detail/VmDetailsPage";
import { WebhooksPage } from "./features/webhooks/WebhooksPage";
import { useDashboardData, useProviderServiceStatus } from "./lib/useProviderData";

type AppRoute = { page: PageId } | { page: "vm-detail"; vmId: string };

export function App() {
  const [route, setRoute] = React.useState<AppRoute>({ page: "overview" });
  const service = useProviderServiceStatus();
  const dashboard = useDashboardData(service.status?.running);

  React.useEffect(() => startPricePolling(), []);

  const navigate = React.useCallback((target: NavigateTarget) => {
    setRoute(target);
  }, []);

  if (service.status && !service.status.running) {
    return (
      <ServiceStopped
        error={service.error}
        busy={service.busyAction === "start"}
        onStart={() => void service.runAction("start")}
      />
    );
  }

  return (
    <AppShell
      activePage={route.page}
      data={dashboard.data}
      serviceStatus={service.status}
      busyAction={service.busyAction}
      onNavigate={navigate}
      onStopProvider={() => void service.runAction("stop")}
    >
      {route.page === "overview" ? (
        <OverviewPage
          data={dashboard.data}
          loading={dashboard.loading}
          onNavigate={navigate}
        />
      ) : null}
      {route.page === "vms" ? (
        <VirtualMachinesPage
          data={dashboard.data}
          loading={dashboard.loading}
          onNavigate={navigate}
        />
      ) : null}
      {route.page === "streams" ? (
        <StreamsPage
          data={dashboard.data}
          loading={dashboard.loading}
          onNavigate={navigate}
        />
      ) : null}
      {route.page === "monitoring" ? (
        <MonitoringPage data={dashboard.data} loading={dashboard.loading} />
      ) : null}
      {route.page === "alerts" ? (
        <AlertsPage
          data={dashboard.data}
          loading={dashboard.loading}
          onRefresh={dashboard.refresh}
        />
      ) : null}
      {route.page === "webhooks" ? (
        <WebhooksPage
          data={dashboard.data}
          loading={dashboard.loading}
          onRefresh={dashboard.refresh}
        />
      ) : null}
      {route.page === "vm-detail" ? (
        <VmDetailsPage vmId={route.vmId} onNavigate={navigate} />
      ) : null}
      {route.page === "settings" || route.page === "health" ? (
        <PlaceholderPage page={route.page} />
      ) : null}
    </AppShell>
  );
}

function PlaceholderPage({ page }: { page: "settings" | "health" }) {
  return (
    <div className="space-y-6">
      <PageHeader
        title={page === "settings" ? "Settings" : "Health"}
        description="This provider endpoint is not exposed to the desktop app yet."
      />
      <Card>
        <CardBody>
          <p className="text-sm text-text-secondary">
            The sidebar entry is present for the provider workflow, but this screen
            needs a backend contract before it can be data-driven.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
