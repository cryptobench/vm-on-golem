import React from "react";
import ReactDOM from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import { Buffer } from "buffer";
import {
  setRequestorRuntimeConfig,
  type RequestorRuntimeConfig,
} from "../../../requestor-web/lib/runtimeConfig";
import "./styles.css";

if (typeof window !== "undefined") {
  if (!(globalThis as unknown as { Buffer?: typeof Buffer }).Buffer) {
    (globalThis as unknown as { Buffer: typeof Buffer }).Buffer = Buffer;
  }
}

async function loadDesktopRuntimeConfig() {
  try {
    const config = await invoke<RequestorRuntimeConfig>(
      "requestor_runtime_config",
    );
    setRequestorRuntimeConfig(config);
  } catch (error) {
    console.warn("Requestor desktop runtime config unavailable", error);
  }
}

async function bootstrap() {
  await loadDesktopRuntimeConfig();
  const { App } = await import("./App");

  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void bootstrap();
