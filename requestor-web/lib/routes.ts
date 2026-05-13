export function vmDetailsHref(vmId: string) {
  return `/vm/${encodeURIComponent(vmId)}`;
}
