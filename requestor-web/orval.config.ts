import { defineConfig } from "orval";

const output = {
  client: "fetch" as const,
  mode: "single" as const,
  prettier: true,
  headers: false,
  override: {
    mutator: {
      path: "lib/api/orval-fetch.ts",
      name: "orvalFetch",
    },
  },
};

export default defineConfig({
  centralDiscovery: {
    input: "../openapi/central-discovery.json",
    output: {
      ...output,
      target: "lib/generated/api/central-discovery.ts",
    },
  },
  provider: {
    input: "../openapi/provider.json",
    output: {
      ...output,
      target: "lib/generated/api/provider.ts",
    },
  },
});
