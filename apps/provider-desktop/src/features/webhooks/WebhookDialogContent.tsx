import type {
  WebhookConfig,
  WebhookTestResponse,
} from "../../lib/types";
import { BasicsStep, EventsStep } from "./BasicsEventsStep";
import { ReviewStep } from "./ReviewStep";
import type { DialogStep, WebhookFormSetter } from "./webhookTypes";

export function WebhookDialogContent({
  step,
  form,
  testResult,
  onFormChange,
}: {
  step: DialogStep;
  form: WebhookConfig;
  testResult: WebhookTestResponse | null;
  onFormChange: WebhookFormSetter;
}) {
  if (step === "review") {
    return (
      <ReviewStep
        form={form}
        testResult={testResult}
      />
    );
  }

  if (step === "events") {
    return <EventsStep form={form} onFormChange={onFormChange} />;
  }

  return <BasicsStep form={form} onFormChange={onFormChange} />;
}
