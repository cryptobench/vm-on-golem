import { Button } from "@golem/ui";
import type { WebhookConfig } from "../../lib/types";
import { ServiceIcon } from "./WebhookServiceVisuals";
import type { DialogStep } from "./webhookTypes";
import { serviceLabel } from "./webhookUtils";

export function WebhookDialogFooter({
  form,
  step,
  saving,
  testing,
  canContinue,
  previousStep,
  nextStep,
  onClose,
  onStepChange,
  onSave,
  onTest,
  onDelete,
}: {
  form: WebhookConfig;
  step: DialogStep;
  saving: boolean;
  testing: boolean;
  canContinue: boolean;
  previousStep: DialogStep;
  nextStep: DialogStep;
  onClose: () => void;
  onStepChange: (step: DialogStep) => void;
  onSave: () => void;
  onTest: () => void;
  onDelete?: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center justify-between border-t border-border px-8 py-5">
      <DialogSummary form={form} />
      <div className="flex items-center gap-3">
        {step === "review" && form.id != null ? (
          <Button variant="secondary" busy={testing} onClick={onTest}>
            Test webhook
          </Button>
        ) : null}
        {step === "review" && onDelete ? (
          <Button variant="danger" onClick={onDelete}>
            Delete
          </Button>
        ) : null}
        <Button
          variant="secondary"
          onClick={step === "basics" ? onClose : () => onStepChange(previousStep)}
        >
          {step === "basics" ? "Cancel" : "Back"}
        </Button>
        {step === "review" ? (
          <Button busy={saving} disabled={!canContinue} onClick={onSave}>
            Save webhook
          </Button>
        ) : (
          <Button disabled={!canContinue} onClick={() => onStepChange(nextStep)}>
            Continue
          </Button>
        )}
      </div>
    </div>
  );
}

function DialogSummary({ form }: { form: WebhookConfig }) {
  return (
    <div className="flex min-w-0 items-center gap-3 text-sm font-medium text-text-secondary">
      <ServiceIcon type={form.service_type} />
      <span>Service: {serviceLabel(form.service_type)}</span>
      <span className="text-text-muted">|</span>
      <span>{form.events.length} events selected</span>
    </div>
  );
}
