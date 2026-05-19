import assert from "node:assert/strict";
import test from "node:test";

import { formatLocalTime, parseAbsoluteTimestamp } from "./time";

test("requires explicit timezone-bearing timestamps", () => {
  assert.equal(parseAbsoluteTimestamp("2026-05-14T19:31:00"), null);
  assert.equal(
    parseAbsoluteTimestamp("2026-05-14T19:31:00+00:00"),
    Date.UTC(2026, 4, 14, 19, 31),
  );
});

test("formats with the system locale", () => {
  const original = Intl.DateTimeFormat;
  let localeArgument: unknown = "not-called";
  class CapturingDateTimeFormat extends original {
    constructor(locales?: Intl.LocalesArgument, options?: Intl.DateTimeFormatOptions) {
      localeArgument = locales;
      super(locales, options);
    }
  }
  Intl.DateTimeFormat = CapturingDateTimeFormat as typeof Intl.DateTimeFormat;
  try {
    assert.equal(
      typeof formatLocalTime("2026-05-14T19:31:00+00:00"),
      "string",
    );
    assert.equal(localeArgument, undefined);
  } finally {
    Intl.DateTimeFormat = original;
  }
});
