import React from "react";
import { invoke } from "@tauri-apps/api/core";
import { Button, Callout, PageHeader, Skeleton, StatusBadge } from "@golem/ui";

type ProviderStatus = {
  running: boolean;
  apiBaseUrl: string;
};

async function getProviderStatus() {
  return invoke<ProviderStatus>("provider_status");
}

export function App() {
  const [status, setStatus] = React.useState<ProviderStatus | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busyAction, setBusyAction] = React.useState<"start" | "stop" | null>(null);

  const refresh = React.useCallback(async () => {
    try {
      setError(null);
      setStatus(await getProviderStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  React.useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const runAction = async (action: "start" | "stop") => {
    setBusyAction(action);
    setError(null);
    try {
      await invoke(action === "start" ? "start_provider" : "stop_provider");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <PageHeader
        title="Golem Provider"
        description="Start the local provider service and monitor whether the bundled provider API is reachable."
      />

      <section className="card">
        <div className="card-body flex flex-col gap-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-text-primary">
                Provider service
              </h2>
              <p className="mt-1 text-sm text-text-secondary">
                {status ? status.apiBaseUrl : "Checking provider API"}
              </p>
            </div>
            {status ? (
              <StatusBadge
                label={status.running ? "Running" : "Stopped"}
                tone={status.running ? "success" : "neutral"}
              />
            ) : (
              <Skeleton className="h-6 w-24 rounded-full" />
            )}
          </div>

          {error ? (
            <Callout tone="danger">
              Provider command failed: {error}
            </Callout>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => runAction("start")}
              busy={busyAction === "start"}
              disabled={busyAction !== null || status?.running}
            >
              Start Provider
            </Button>
            <Button
              variant="secondary"
              onClick={() => runAction("stop")}
              busy={busyAction === "stop"}
              disabled={busyAction !== null || !status?.running}
            >
              Stop Provider
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
}
