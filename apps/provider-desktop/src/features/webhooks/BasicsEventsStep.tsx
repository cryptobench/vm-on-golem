import { FormField, Input } from "@golem/ui";
import type { WebhookConfig } from "../../lib/types";
import { EventCard } from "./EventCard";
import { ServiceCard } from "./WebhookServiceVisuals";
import { WEBHOOK_EVENTS } from "./webhookConstants";
import type { WebhookFormSetter } from "./webhookTypes";
import { isValidWebhookUrl, toggleEvent } from "./webhookUtils";

export function BasicsStep({
  form,
  onFormChange,
}: {
  form: WebhookConfig;
  onFormChange: WebhookFormSetter;
}) {
  return (
    <section>
      <div className="grid gap-10 xl:grid-cols-[minmax(0,32rem)_minmax(20rem,1fr)]">
        <div>
          <h3 className="text-xl font-semibold text-text-primary">Basics</h3>
          <p className="mt-4 max-w-xl text-sm text-text-secondary">
            Provide the destination and basic settings for this webhook.
          </p>
          <div className="mt-7 max-w-xl space-y-6">
            <FormField label="Webhook name">
              <Input
                value={form.name}
                onChange={(event) =>
                  onFormChange({ ...form, name: event.target.value })
                }
              />
            </FormField>
            <FormField label="Destination URL">
              <Input
                type="url"
                value={form.url}
                placeholder="https://hooks.slack.com/services/..."
                hasError={
                  form.url.trim().length > 0 && !isValidWebhookUrl(form.url)
                }
                onChange={(event) =>
                  onFormChange({ ...form, url: event.target.value })
                }
              />
              {form.url.trim().length > 0 && !isValidWebhookUrl(form.url) ? (
                <div className="mt-2 text-sm text-danger">
                  Enter a valid HTTP or HTTPS URL.
                </div>
              ) : null}
            </FormField>
          </div>
        </div>
        <ServiceTypePicker form={form} onFormChange={onFormChange} />
      </div>
    </section>
  );
}

export function EventsStep({
  form,
  onFormChange,
}: {
  form: WebhookConfig;
  onFormChange: WebhookFormSetter;
}) {
  return (
    <section>
      <h3 className="text-xl font-semibold text-text-primary">Events</h3>
      <p className="mt-4 text-sm text-text-secondary">
        Select which events will trigger this webhook.
      </p>
      <div className="mt-7 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {WEBHOOK_EVENTS.map((event) => (
          <EventCard
            key={event.id}
            event={event}
            selected={form.events.includes(event.id)}
            onChange={(checked) =>
              onFormChange({
                ...form,
                events: toggleEvent(form.events, event.id, checked),
              })
            }
          />
        ))}
      </div>
      <p className="mt-6 text-sm leading-6 text-text-secondary">
        Selected events will trigger this webhook. You can customize the message
        content in the next step.
      </p>
    </section>
  );
}

function ServiceTypePicker({
  form,
  onFormChange,
}: {
  form: WebhookConfig;
  onFormChange: WebhookFormSetter;
}) {
  return (
    <div>
      <div className="label">Service type</div>
      <div className="mt-2 grid gap-4 sm:grid-cols-2">
        {(["slack", "discord", "generic_json"] as const).map((type) => (
          <ServiceCard
            key={type}
            type={type}
            selected={form.service_type === type}
            onSelect={() => onFormChange({ ...form, service_type: type })}
          />
        ))}
      </div>
    </div>
  );
}
