import assert from "node:assert/strict";
import test from "node:test";

import { buildSshCommand, copyText } from "./ssh";

function setGlobal(name: "document" | "navigator", value: unknown) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    value,
  });
}

function clearClipboardGlobals() {
  delete (globalThis as { document?: unknown }).document;
  delete (globalThis as { navigator?: unknown }).navigator;
}

test.afterEach(() => {
  clearClipboardGlobals();
});

test("builds the SSH command", () => {
  assert.equal(
    buildSshCommand("203.0.113.10", 2222, "ubuntu"),
    "ssh ubuntu@203.0.113.10 -p 2222",
  );
});

test("copies with the Clipboard API when available", async () => {
  let copied = "";
  setGlobal("navigator", {
    clipboard: {
      writeText: async (value: string) => {
        copied = value;
      },
    },
  });

  assert.equal(await copyText("ssh ubuntu@example -p 22"), true);
  assert.equal(copied, "ssh ubuntu@example -p 22");
});

test("falls back to textarea copy when Clipboard API is unavailable", async () => {
  let selected = "";
  let appended = false;
  let removed = false;
  const textarea = {
    value: "",
    style: {},
    setAttribute() {},
    select() {
      selected = this.value;
    },
  };

  setGlobal("document", {
    body: {
      appendChild(node: typeof textarea) {
        appended = node === textarea;
      },
      removeChild(node: typeof textarea) {
        removed = node === textarea;
      },
    },
    createElement(tagName: string) {
      assert.equal(tagName, "textarea");
      return textarea;
    },
    execCommand(command: string) {
      assert.equal(command, "copy");
      return true;
    },
    getSelection() {
      return null;
    },
  });

  assert.equal(await copyText("ssh ubuntu@example -p 22"), true);
  assert.equal(selected, "ssh ubuntu@example -p 22");
  assert.equal(appended, true);
  assert.equal(removed, true);
});
