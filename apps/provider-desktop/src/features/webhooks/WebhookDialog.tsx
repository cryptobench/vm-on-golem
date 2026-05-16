import { Modal } from "@golem/ui";
import type {
  WebhookConfig,
  WebhookDeliveryAttempt,
  WebhookTestResponse,
} from "../../lib/types";
import { WebhookDialogContent } from "./WebhookDialogContent";
import { WebhookDialogFooter } from "./WebhookDialogFooter";
import { WebhookDialogHeader } from "./WebhookDialogHeader";
import { WebhookStepper } from "./WebhookStepper";
import { DIALOG_STEPS } from "./webhookConstants";
import type { DialogStep, WebhookFormSetter } from "./webhookTypes";
import { isValidWebhookUrl } from "./webhookUtils";

export function WebhookDialog({
  open,
  form,
  step,
  deliveries,
  saving,
  testing,
  testResult,
  onClose,
  onFormChange,
  onStepChange,
  onSave,
  onTest,
  onDelete,
}: {
  open: boolean;
  form: WebhookConfig;
  step: DialogStep;
  deliveries: WebhookDeliveryAttempt[];
  saving: boolean;
  testing: boolean;
  testResult: WebhookTestResponse | null;
  onClose: () => void;
  onFormChange: WebhookFormSetter;
  onStepChange: (step: DialogStep) => void;
  onSave: () => void;
  onTest: () => void;
  onDelete?: () => void;
}) {
  const currentIndex = Math.max(
    0,
    DIALOG_STEPS.findIndex((item) => item.id === step),
  );
  const nextStep = DIALOG_STEPS[Math.min(currentIndex + 1, lastStepIndex())];
  const previousStep = DIALOG_STEPS[Math.max(currentIndex - 1, 0)];
  const basicsComplete =
    Boolean(form.name.trim()) && isValidWebhookUrl(form.url);
  const eventsComplete = form.events.length > 0;
  const canContinue =
    step === "basics"
      ? basicsComplete
      : step === "events"
        ? eventsComplete
        : basicsComplete && eventsComplete;

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="6xl"
      className="max-h-[calc(100vh-3rem)] overflow-hidden rounded-lg"
    >
      <div className="flex max-h-[calc(100vh-3rem)] flex-col">
        <WebhookDialogHeader editing={form.id != null} onClose={onClose} />
        <div className="shrink-0 px-8 pt-8">
          <WebhookStepper step={step} onStepChange={onStepChange} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-8 py-8">
          <WebhookDialogContent
            step={step}
            form={form}
            testResult={testResult}
            onFormChange={onFormChange}
          />
        </div>
        <WebhookDialogFooter
          form={form}
          step={step}
          saving={saving}
          testing={testing}
          canContinue={canContinue}
          previousStep={previousStep.id}
          nextStep={nextStep.id}
          onClose={onClose}
          onStepChange={onStepChange}
          onSave={onSave}
          onTest={onTest}
          onDelete={onDelete}
        />
      </div>
    </Modal>
  );
}

function lastStepIndex() {
  return DIALOG_STEPS.length - 1;
}
