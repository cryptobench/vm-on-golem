import { Button, PageHeader } from "@golem/ui";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import type { DashboardData } from "../../lib/useProviderData";
import { WebhookDialog } from "./WebhookDialog";
import { WebhookFilters } from "./WebhookFilters";
import { WebhooksTable } from "./WebhooksTable";
import { useWebhooksController } from "./useWebhooksController";

export function WebhooksPage({
  data,
  loading,
  onRefresh,
}: {
  data: DashboardData | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const controller = useWebhooksController({ data, onRefresh });

  if (loading && !data) return <LoadingGrid />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Webhooks"
        description="Webhooks send automated notifications to external services when events happen."
        actions={
          <Button onClick={controller.openCreateDialog}>Create webhook</Button>
        }
      />
      <EndpointErrors
        errors={{
          ...(data?.errors ?? {}),
          ...(controller.error ? { webhook: controller.error } : {}),
        }}
      />

      <WebhookFilters
        search={controller.search}
        serviceFilter={controller.serviceFilter}
        statusFilter={controller.statusFilter}
        onSearchChange={controller.setSearch}
        onServiceFilterChange={controller.setServiceFilter}
        onStatusFilterChange={controller.setStatusFilter}
      />

      <WebhooksTable
        webhooks={controller.filtered}
        pendingToggleIds={controller.pendingToggleIds}
        onToggle={(webhook, enabled) =>
          void controller.toggleEnabled(webhook, enabled)
        }
        onEdit={(webhook) => void controller.openEditDialog(webhook)}
        onTest={(webhook) => void controller.openTestDialog(webhook)}
        onDelete={(id) => void controller.remove(id)}
      />

      <WebhookDialog
        open={controller.dialogOpen}
        form={controller.form}
        step={controller.step}
        deliveries={controller.deliveries}
        saving={controller.saving}
        testing={controller.testing}
        testResult={controller.testResult}
        onClose={() => controller.setDialogOpen(false)}
        onFormChange={controller.setForm}
        onStepChange={controller.setStep}
        onSave={controller.save}
        onTest={controller.test}
        onDelete={
          controller.form.id == null
            ? undefined
            : () => void controller.remove(controller.form.id!)
        }
      />
    </div>
  );
}
