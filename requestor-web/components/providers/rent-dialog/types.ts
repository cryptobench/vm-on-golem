export type RentSpec = {
  cpu: number;
  memory: number;
  storage: number;
};

export type DurationPreset = "1w" | "2w" | "30d" | "custom";

export type DurationOption = {
  preset: Exclude<DurationPreset, "custom">;
  label: string;
  seconds: number;
};

export type PriceLine = {
  primary: string;
  secondary?: string;
};
