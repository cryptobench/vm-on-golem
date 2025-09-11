import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9ecff',
          200: '#bfe0ff',
          300: '#94cdff',
          400: '#5db1ff',
          500: '#328fff',
          600: '#1f6fff',
          700: '#1458f5',
          800: '#1245c4',
          900: '#123b9a',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}

export default config

