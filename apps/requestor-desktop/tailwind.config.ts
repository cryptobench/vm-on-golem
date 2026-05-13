import type { Config } from "tailwindcss";
import golemPreset from "@golem/design-system/tailwind-preset";

const config: Config = {
  presets: [golemPreset],
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "../../requestor-web/app/**/*.{js,ts,jsx,tsx,mdx}",
    "../../requestor-web/components/**/*.{js,ts,jsx,tsx,mdx}",
    "../../requestor-web/context/**/*.{js,ts,jsx,tsx,mdx}",
    "../../requestor-web/hooks/**/*.{js,ts,jsx,tsx,mdx}",
    "../../requestor-web/lib/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/design-system/**/*.{js,ts,jsx,tsx,mdx}",
    "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}",
    "../../node_modules/@tremor/**/*.{js,ts,jsx,tsx}",
  ],
  safelist: [
    { pattern: /^(bg-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(text-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(border-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(ring-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(stroke-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(fill-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
  ],
  plugins: [require("@headlessui/tailwindcss"), require("@tailwindcss/forms")],
};

export default config;
