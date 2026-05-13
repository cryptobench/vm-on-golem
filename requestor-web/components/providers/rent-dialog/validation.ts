import type { DurationPreset } from "./types";

export function getStepDisabledReason({
  step,
  name,
  sshKey,
  durationSeconds,
  preset,
  customInput,
}: {
  step: number;
  name: string;
  sshKey: string;
  durationSeconds: number;
  preset: DurationPreset | "24h";
  customInput: string;
}) {
  if (step >= 1 && !durationSeconds) {
    if (preset === "custom" && customInput.trim()) {
      return "Enter a valid custom duration to continue.";
    }
    return "Select a valid rental duration to continue.";
  }
  if (step >= 2 && !name.trim()) return "Enter a VM name to continue.";
  if (step >= 2 && !sshKey.trim())
    return "Select or add an SSH key to continue.";
  return "";
}
