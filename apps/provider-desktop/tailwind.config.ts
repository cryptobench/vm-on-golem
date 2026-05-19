import type { Config } from "tailwindcss";
import golemPreset from "@golem/design-system/tailwind-preset";

const config: Config = {
  presets: [golemPreset],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
    "../../packages/design-system/**/*.{js,ts,jsx,tsx}",
  ],
};

export default config;
