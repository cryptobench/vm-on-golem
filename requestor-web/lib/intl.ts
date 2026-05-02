const REGION_NAMES =
  typeof Intl !== "undefined" ? new Intl.DisplayNames(["en"], { type: "region" }) : null;

export function countryFullName(code: string | null | undefined) {
  if (!code) return "";
  try {
    return REGION_NAMES?.of(code.toUpperCase()) || code.toUpperCase();
  } catch {
    return code.toUpperCase();
  }
}

export function countryFlagEmoji(code: string | null | undefined) {
  if (!code || code.length !== 2) return "";
  const upper = code.toUpperCase();
  return upper
    .split("")
    .map((char) => String.fromCodePoint(127397 + char.charCodeAt(0)))
    .join("");
}
