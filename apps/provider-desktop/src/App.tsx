import React from "react";
import { Card, CardBody, PageHeader } from "@golem/ui";
import { startPricePolling } from "@golem/prices";
import { AppShell } from "./components/AppShell";
import { ServiceStopped, isStartupSetupComplete } from "./components/StateViews";
import type { NavigateTarget, PageId } from "./components/types";
import { AlertsPage } from "./features/alerts/AlertsPage";
import { MonitoringPage } from "./features/monitoring/MonitoringPage";
import { OverviewPage } from "./features/overview/OverviewPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { StreamsPage } from "./features/streams/StreamsPage";
import { VirtualMachinesPage } from "./features/vms/VirtualMachinesPage";
import { VmDetailsPage } from "./features/vm-detail/VmDetailsPage";
import { WebhooksPage } from "./features/webhooks/WebhooksPage";
import { useDashboardData, useProviderServiceStatus } from "./lib/useProviderData";

type AppRoute = { page: PageId } | { page: "vm-detail"; vmId: string };

export function App() {
  const [route, setRoute] = React.useState<AppRoute>({ page: "overview" });
  const service = useProviderServiceStatus();
  const autoStartAttempted = React.useRef(false);
  const setupComplete = service.setupStatus
    ? isStartupSetupComplete(service.setupStatus)
    : false;
  const serviceReady =
    service.status?.running === true && service.status.adminAuthenticated === true;
  const startupReadyForDashboard =
    !service.error && setupComplete && serviceReady;
  const [startupHandoffComplete, setStartupHandoffComplete] = React.useState(false);
  const dashboardEnabled = serviceReady;
  const dashboard = useDashboardData(dashboardEnabled);

  React.useEffect(() => startPricePolling(), []);

  React.useEffect(() => {
    if (
      autoStartAttempted.current ||
      !service.status ||
      (service.status.running && service.status.adminAuthenticated) ||
      service.busyAction !== null ||
      service.setupStatus ||
      service.error
    ) {
      return;
    }

    autoStartAttempted.current = true;
    void service.runAction("start");
  }, [
    service.busyAction,
    service.error,
    service.runAction,
    service.setupStatus,
    service.status,
  ]);

  React.useEffect(() => {
    if (!startupReadyForDashboard) {
      setStartupHandoffComplete(false);
      return;
    }

    const id = window.setTimeout(() => setStartupHandoffComplete(true), 420);
    return () => window.clearTimeout(id);
  }, [startupReadyForDashboard]);

  const navigate = React.useCallback((target: NavigateTarget) => {
    setRoute(target);
  }, []);

  if (
    (!service.status && !startupHandoffComplete) ||
    (startupReadyForDashboard && !startupHandoffComplete) ||
    (service.status && !serviceReady && !startupHandoffComplete)
  ) {
    return (
      <ServiceStopped
        error={service.error ?? service.status?.adminAuthError ?? null}
        busy={service.busyAction === "start"}
        setupStatus={service.setupStatus}
        exiting={startupReadyForDashboard}
        onStart={() => void service.runAction("start")}
      />
    );
  }

  return (
    <div className={startupHandoffComplete ? "provider-dashboard-screen" : undefined}>
      <AppShell
        activePage={route.page}
        data={dashboard.data}
        onNavigate={navigate}
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
        {route.page === "settings" ? (
          <SettingsPage
            onRefresh={dashboard.refresh}
          />
        ) : null}
        {route.page === "health" ? (
          <PlaceholderPage page={route.page} />
        ) : null}
      </AppShell>
    </div>
  );
}

function PlaceholderPage({ page }: { page: "health" }) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Health"
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
