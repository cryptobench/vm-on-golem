import { Button, Callout, Card, CardBody, Skeleton } from "@golem/ui";

export function LoadingGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Card key={index}>
          <CardBody className="space-y-4">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-8 w-36" />
            <Skeleton className="h-4 w-24" />
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

export function ServiceStopped({
  error,
  busy,
  onStart,
}: {
  error: string | null;
  busy: boolean;
  onStart: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-5 px-6">
      <div>
        <h1 className="text-2xl font-semibold text-text-primary">Golem Provider</h1>
        <p className="mt-2 text-sm text-text-secondary">
          Start the provider service to load dashboard data.
        </p>
      </div>
      {error ? <Callout tone="danger">Provider command failed: {error}</Callout> : null}
      <Button busy={busy} onClick={onStart}>
        Start Provider
      </Button>
    </div>
  );
}

export function EndpointErrors({ errors }: { errors: Record<string, string> }) {
  const entries = Object.entries(errors);
  if (entries.length === 0) return null;
  return (
    <Callout tone="warning">
      Some provider endpoints could not be loaded:{" "}
      {entries.map(([name, message]) => `${name}: ${message}`).join("; ")}
    </Callout>
  );
}

export function EmptyPanel({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted px-4 py-8 text-center">
      <p className="font-medium text-text-primary">{title}</p>
      {detail ? <p className="mt-1 text-sm text-text-secondary">{detail}</p> : null}
    </div>
  );
}
