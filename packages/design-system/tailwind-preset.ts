import type { Config } from "tailwindcss";
import { colors, radius, shadows, spacing, typography } from "./tokens";

const preset = {
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
} satisfies Partial<Config>;

export default preset;
