import { Card, CardBody, Skeleton } from "@golem/ui";

export function ResourceLimit({
  label,
  value,
  unit,
}: {
  label: string;
  value: number;
  unit: string;
}) {
  return (
    <div className="flex justify-between gap-3">
      <span>{label}</span>
      <span className="font-medium text-text-primary">
        {value} {unit}
      </span>
    </div>
  );
}

export function EarningsLine({
  label,
  detail,
  value,
}: {
  label: string;
  detail: string;
  value: string;
}) {
  return (
    <div className="border-b border-border pb-4 last:border-b-0">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-semibold text-text-primary">{label}</div>
          <div className="mt-1 text-sm text-text-secondary">{detail}</div>
        </div>
        <div className="font-semibold text-text-primary tabular-nums">{value}</div>
      </div>
    </div>
  );
}

export function SettingsSkeleton() {
  return (
    <Card>
      <CardBody className="space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </CardBody>
    </Card>
  );
}
