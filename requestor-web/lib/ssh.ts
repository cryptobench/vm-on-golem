"use client";

export function buildSshCommand(host: string, port: number | string) {
  return `ssh root@${host} -p ${port}`;
}

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
