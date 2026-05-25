const CREATION_STREAM_STATUSES = new Set(["creating"]);

const CREATION_STREAM_STAGES = new Set([
  "queued",
  "allocating_resources",
  "preparing_guest",
  "launching",
  "waiting_for_guest",
  "provisioning",
  "configuring_access",
]);

export function isPaymentStreamPanelLoading({
  streamId,
  hasStream,
  lifecycleStatus,
  lifecycleStage,
}: {
  streamId?: string | number | null;
  hasStream: boolean;
  lifecycleStatus?: string | null;
  lifecycleStage?: string | null;
}) {
  if (streamId == null || streamId === "" || hasStream) return false;

  const status = normalizeLifecyclePart(lifecycleStatus);
  const stage = normalizeLifecyclePart(lifecycleStage);

  return (
    CREATION_STREAM_STATUSES.has(status) || CREATION_STREAM_STAGES.has(stage)
  );
}

function normalizeLifecyclePart(value?: string | null) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_");
}
