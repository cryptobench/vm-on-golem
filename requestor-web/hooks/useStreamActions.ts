"use client";
import { Contract } from "ethers";
import streamPayment from "../public/abi/StreamPayment.json";
import erc20 from "../public/abi/ERC20.json";
import { useWallet } from "../context/WalletContext";
import { getPaymentsSigner, getWalletName } from "../lib/walletClient";

export function useStreamActions(spAddr: string | null | undefined) {
  const { ensurePaymentsNetwork } = useWallet();

  async function topUp(
    streamId: string | number | bigint,
    tokenAddress: string,
    ratePerSecond: bigint,
    seconds: number,
  ) {
    if (!spAddr) throw new Error("StreamPayment address missing");
    const sid = typeof streamId === "bigint" ? streamId : BigInt(streamId);
    const signer = await getPaymentsSigner({ ensurePaymentsNetwork });
    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const addWei = ratePerSecond * BigInt(seconds);
    const token = new Contract(tokenAddress, (erc20 as any).abi, signer);
    const owner = await signer.getAddress();
    const allowance = await token.allowance(owner, spAddr);
    if (allowance < addWei) {
      const approveTx = await token.approve(spAddr, addWei);
      await approveTx.wait();
    }
    const tx = await contract.topUp(sid, addWei, { gasLimit: 150000n });
    await tx.wait();
    return tx.hash as string;
  }

  async function terminate(
    streamId: string | number | bigint,
    onPhase?: (phase: string) => void,
  ) {
    if (!spAddr) throw new Error("StreamPayment address missing");
    const sid = typeof streamId === "bigint" ? streamId : BigInt(streamId);
    const walletName = getWalletName();
    onPhase?.(
      `Waiting for your approval in ${walletName} to terminate the old stream`,
    );
    const signer = await getPaymentsSigner({ ensurePaymentsNetwork });
    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const tx = await contract.terminate(sid, { gasLimit: 180000n });
    onPhase?.(
      "Waiting for old stream termination confirmation on the blockchain",
    );
    await tx.wait();
    return tx.hash as string;
  }

  return { topUp, terminate };
}
