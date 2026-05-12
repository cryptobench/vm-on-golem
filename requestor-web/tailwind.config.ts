import type { Config } from 'tailwindcss'
import { colors, radius, shadows, spacing, typography } from '../design-system/tokens'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './design-system/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
    '../design-system/**/*.{js,ts,jsx,tsx,mdx}',
    // Tremor components
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    borderRadius: radius,
    extend: {
      colors,
      boxShadow: shadows,
      fontFamily: typography.fontFamily,
      fontSize: typography.fontSize,
      spacing,
    },
  },
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
