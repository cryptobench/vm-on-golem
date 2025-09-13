"use client";
import { BrowserProvider, Contract } from "ethers";
import { ensureNetwork, getPaymentsChain } from "../lib/chain";
import streamPayment from "../public/abi/StreamPayment.json";

export function useStreamActions(spAddr: string | null | undefined) {
  async function topUp(streamId: string | number | bigint, tokenAddress: string, ratePerSecond: bigint, seconds: number) {
    if (!spAddr) throw new Error('StreamPayment address missing');
    const sid = typeof streamId === 'bigint' ? streamId : BigInt(streamId);
    const { ethereum } = window as any;
    await ensureNetwork(ethereum, getPaymentsChain());
    const provider = new BrowserProvider(ethereum);
    const signer = await provider.getSigner();
    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const addWei = ratePerSecond * BigInt(seconds);
    const zero = '0x0000000000000000000000000000000000000000';
    const native = (tokenAddress || '').toLowerCase() === zero;
    const tx = await contract.topUp(sid, addWei, { value: native ? addWei : 0n, gasLimit: 150000n });
    await tx.wait();
    return tx.hash as string;
  }
  return { topUp };
}

