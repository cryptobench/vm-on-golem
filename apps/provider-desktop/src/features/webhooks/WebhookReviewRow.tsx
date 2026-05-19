import type React from "react";

export function ReviewRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-4 border-b border-border pb-4 last:border-b-0">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="min-w-0 break-words font-medium text-text-primary">
        {value}
      </dd>
    </div>
  );
}
