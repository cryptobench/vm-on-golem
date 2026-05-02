"use client";

import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../public/abi/StreamPayment.json";
import erc20 from "../public/abi/ERC20.json";
import { getPriceUSD } from "./prices";

export type ChainStream = {
  token: string;
  sender: string;
  recipient: string;
  startTime: bigint;
  stopTime: bigint;
  ratePerSecond: bigint;
  deposit: bigint;
  withdrawn: bigint;
  halted: boolean;
};

export function humanDuration(totalSec: number | bigint): string {
  const seconds = Math.max(0, Number(totalSec));
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m) parts.push(`${m}m`);
  if (s && !parts.length) parts.push(`${s}s`);
  return parts.join(" ") || "0s";
}

export async function fetchStreamWithMeta(spAddr: string, streamId: bigint) {
  const { ethereum } = window as any;
  if (!ethereum) throw new Error("wallet unavailable");
  const provider = new BrowserProvider(ethereum);
  const contract = new Contract(spAddr, (streamPayment as any).abi, provider);
  const chain = (await contract.streams(streamId)) as ChainStream;
  const block = await provider.getBlock("latest");
  const now = BigInt(block?.timestamp || Math.floor(Date.now() / 1000));
  const remaining = chain.stopTime > now && !chain.halted ? chain.stopTime - now : 0n;
  const zero = "0x0000000000000000000000000000000000000000";
  let tokenSymbol = chain.token.toLowerCase() === zero ? "ETH" : "GLM";
  let tokenDecimals = 18;
  if (chain.token.toLowerCase() !== zero) {
    try {
      const token = new Contract(chain.token, (erc20 as any).abi, provider);
      tokenSymbol = await token.symbol();
      tokenDecimals = Number(await token.decimals());
    } catch {
      tokenSymbol = "GLM";
    }
  }
  return {
    chain,
    remaining,
    tokenSymbol,
    tokenDecimals,
    usdPrice: getPriceUSD(tokenSymbol),
  };
}
