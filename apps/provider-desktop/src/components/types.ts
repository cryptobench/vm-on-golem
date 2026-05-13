export type PageId =
  | "overview"
  | "vms"
  | "streams"
  | "monitoring"
  | "alerts"
  | "webhooks"
  | "settings"
  | "health";

export type NavigateTarget =
  | { page: PageId }
  | { page: "vm-detail"; vmId: string };
