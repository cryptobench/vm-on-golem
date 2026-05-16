import { StatusBadge } from "@golem/ui";
import { EMPTY_VALUE } from "../../lib/format";
import type {
  WebhookConfig,
  WebhookTestResponse,
} from "../../lib/types";
import { WEBHOOK_EVENTS } from "./webhookConstants";
import { serviceLabel } from "./webhookUtils";

export function ReviewStep({
  form,
  testResult,
}: {
  form: WebhookConfig;
  testResult: WebhookTestResponse | null;
}) {
  const selectedEventOptions = WEBHOOK_EVENTS.filter((item) =>
    form.events.includes(item.id),
  );

  return (
    <div>
      <section>
        <h3 className="text-xl font-semibold text-text-primary">Review</h3>
        <ReviewSummary form={form} />
        <SelectedEvents events={selectedEventOptions} />
        {testResult ? <TestResult result={testResult} /> : null}
      </section>
    </div>
  );
}

function ReviewSummary({ form }: { form: WebhookConfig }) {
  return (
    <dl className="mt-5 grid gap-3 rounded-md border border-border bg-surface px-4 py-4 text-sm md:grid-cols-3">
      <SummaryItem label="Name" value={form.name} />
      <SummaryItem label="Service" value={serviceLabel(form.service_type)} />
      <SummaryItem label="Destination" value={form.url || EMPTY_VALUE} />
    </dl>
  );
}

function SummaryItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase text-text-muted">{label}</dt>
      <dd className="mt-1 truncate font-semibold text-text-primary" title={value}>
        {value}
      </dd>
    </div>
  );
}

function SelectedEvents({ events }: { events: typeof WEBHOOK_EVENTS }) {
  return (
    <div className="mt-5">
      <h4 className="text-sm font-semibold text-text-primary">
        Events this webhook will receive
      </h4>
      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {events.map((event) => {
          const Icon = event.icon;

          return (
            <div
              key={event.id}
              className="flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-3 py-2"
            >
              <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-text-primary">
                  {event.label}
                </div>
                <div className="truncate text-xs text-text-secondary">
                  {event.description}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TestResult({ result }: { result: WebhookTestResponse }) {
  return (
    <div className="mt-6 rounded-md border border-border p-4">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-text-primary">Test result</div>
        <StatusBadge
          label={result.ok ? "Success" : "Failed"}
          tone={result.ok ? "success" : "danger"}
        />
      </div>
      <div className="mt-3 text-sm text-text-secondary">
        HTTP {result.status ?? EMPTY_VALUE}
      </div>
      {result.error ? (
        <div className="mt-2 text-sm text-danger">{result.error}</div>
      ) : null}
    </div>
  );
}
