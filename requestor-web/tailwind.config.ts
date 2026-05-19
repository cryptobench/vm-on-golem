import type { Config } from 'tailwindcss'
import golemPreset from '@golem/design-system/tailwind-preset'

const config: Config = {
  presets: [golemPreset],
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
    '../packages/ui/src/**/*.{js,ts,jsx,tsx,mdx}',
    '../packages/design-system/**/*.{js,ts,jsx,tsx,mdx}',
    // Tremor components
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  safelist: [
    { pattern: /^(bg-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(text-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(border-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(ring-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(stroke-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
    { pattern: /^(fill-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950))$/ },
  ],
  plugins: [require('@headlessui/tailwindcss'), require('@tailwindcss/forms')],
}

export default config
