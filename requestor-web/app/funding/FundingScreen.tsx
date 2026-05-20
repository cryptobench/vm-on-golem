"use client";

import React from "react";
import { Contract } from "ethers";
import {
  RiArrowRightUpLine,
  RiCopperCoinLine,
  RiFileCopyLine,
  RiWallet3Line,
} from "@remixicon/react";
import {
  Alert,
  Button,
  Card,
  CardBody,
  KeyValueList,
  PageHeader,
  Skeleton,
  StatCard,
  useToast,
} from "@golem/ui";
import erc20 from "../../public/abi/ERC20.json";
import { useWallet } from "../../context/WalletContext";
import {
  explorerTxUrl,
  formatNativeBalance,
  formatTokenBalance,
  getFundingConfig,
  TGLM_MINTER_ABI,
} from "../../lib/funding";
import { getPaymentsSigner, getWalletName } from "../../lib/walletClient";

type BalanceState = {
  native: bigint | null;
  token: bigint | null;
  tokenSymbol: string;
  tokenDecimals: number;
};

type BusyState = "connect" | "mint" | null;

function shortAddress(address: string | null) {
  return address
    ? `${address.slice(0, 6)}...${address.slice(-4)}`
    : "Not connected";
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return String(error || "Funding action failed.");
}

async function readTokenSymbol(token: Contract): Promise<string> {
  try {
    return String(await token.symbol()) || "tGLM";
  } catch {
    return "tGLM";
  }
}

async function readTokenDecimals(token: Contract): Promise<number> {
  try {
    const decimals = Number(await token.decimals());
    return Number.isFinite(decimals) ? decimals : 18;
  } catch {
    return 18;
  }
}

export default function FundingScreen() {
  const wallet = useWallet();
  const { show } = useToast();
  const [mounted, setMounted] = React.useState(false);
  const [busy, setBusy] = React.useState<BusyState>(null);
  const [phase, setPhase] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [txHash, setTxHash] = React.useState<string | null>(null);
  const [balances, setBalances] = React.useState<BalanceState>({
    native: null,
    token: null,
    tokenSymbol: "tGLM",
    tokenDecimals: 18,
  });

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const fundingConfig = React.useMemo(() => getFundingConfig(), [mounted]);
  const txUrl = txHash ? explorerTxUrl(fundingConfig.explorerUrl, txHash) : "";
  const hasNativeGas = balances.native === null || balances.native > 0n;

  const refreshBalances = React.useCallback(
    async () => {
      if (
        !wallet.account ||
        !wallet.paymentReady ||
        !fundingConfig.tokenAddress
      ) {
        setBalances((current) => ({ ...current, native: null, token: null }));
        return;
      }
      setError(null);
      try {
        const signer = await getPaymentsSigner({
          account: wallet.account,
          ensurePaymentsNetwork: wallet.ensurePaymentsNetwork,
        });
        const owner = await signer.getAddress();
        const token = new Contract(
          fundingConfig.tokenAddress,
          (erc20 as any).abi,
          signer,
        );
        const [native, tokenBalance, tokenSymbol, tokenDecimals] =
          await Promise.all([
            signer.provider!.getBalance(owner),
            token.balanceOf(owner),
            readTokenSymbol(token),
            readTokenDecimals(token),
          ]);
        setBalances({
          native,
          token: BigInt(tokenBalance),
          tokenSymbol,
          tokenDecimals,
        });
        setPhase(null);
      } catch (refreshError) {
        const message = errorMessage(refreshError);
        setError(message);
        setPhase(null);
      }
    },
    [
      fundingConfig.tokenAddress,
      wallet.account,
      wallet.ensurePaymentsNetwork,
      wallet.paymentReady,
    ],
  );

  React.useEffect(() => {
    if (!mounted) return;
    refreshBalances();
  }, [mounted, refreshBalances]);

  React.useEffect(() => {
    if (!mounted || !wallet.paymentReady) return;
    const onFocus = () => refreshBalances();
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refreshBalances();
    };
    const interval = window.setInterval(() => refreshBalances(), 30000);
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [mounted, refreshBalances, wallet.paymentReady]);

  const connectWallet = async () => {
    setBusy("connect");
    setError(null);
    try {
      await wallet.connect();
      await wallet.refresh();
    } catch (connectError) {
      setError(errorMessage(connectError));
    } finally {
      setBusy(null);
    }
  };

  const copyAddress = async () => {
    if (!wallet.account) return;
    try {
      await navigator.clipboard.writeText(wallet.account);
      show("Wallet address copied.");
    } catch (copyError) {
      show(errorMessage(copyError));
    }
  };

  const mintTglm = async () => {
    setBusy("mint");
    setError(null);
    setTxHash(null);
    try {
      setPhase(`Waiting for approval in ${getWalletName()} to mint tGLM`);
      const signer = await getPaymentsSigner({
        account: wallet.account,
        ensurePaymentsNetwork: wallet.ensurePaymentsNetwork,
      });
      const minter = new Contract(
        fundingConfig.minterAddress,
        TGLM_MINTER_ABI,
        signer,
      );
      const tx = await minter.create();
      setTxHash(tx.hash);
      setPhase("Waiting for tGLM mint confirmation on Hoodi");
      await tx.wait();
      setPhase("Updating balances");
      await refreshBalances();
      setPhase(null);
      show("tGLM minted to the connected wallet.");
    } catch (mintError) {
      setError(errorMessage(mintError));
      setPhase(null);
    } finally {
      setBusy(null);
    }
  };

  if (!mounted) {
    return (
      <div className="space-y-6">
        <PageHeader title="Funding" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  const actionLabel = !wallet.isInstalled
    ? "Install MetaMask"
    : !wallet.isConnected
      ? "Connect wallet"
      : !wallet.paymentReady
        ? "Switch network"
        : "Mint 1000 tGLM";

  const action = !wallet.isInstalled
    ? () =>
        window.open(
          "https://metamask.io/download/",
          "_blank",
          "noopener,noreferrer",
        )
    : !wallet.isConnected || !wallet.paymentReady
      ? connectWallet
      : mintTglm;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Funding"
        description="Prepare your wallet with Hoodi ETH for gas and Hoodi tGLM for payment streams."
      />

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {phase ? <Alert tone="info">{phase}</Alert> : null}
      {!hasNativeGas && wallet.paymentReady ? (
        <Alert tone="warning">
          The connected wallet has no Hoodi ETH for gas. Use the Hoodi PoW faucet
          before minting tGLM.
        </Alert>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-3">
        <StatCard
          label="Connected wallet"
          value={shortAddress(wallet.account)}
          detail={wallet.expectedChain.chainName}
          icon={<RiWallet3Line className="h-5 w-5" aria-hidden />}
          tone={wallet.paymentReady ? "success" : "warning"}
        />
        <StatCard
          label="Hoodi ETH"
          value={formatNativeBalance(balances.native)}
          detail="Required for transaction gas"
          icon={<RiCopperCoinLine className="h-5 w-5" aria-hidden />}
          tone={hasNativeGas ? "success" : "warning"}
        />
        <StatCard
          label={balances.tokenSymbol}
          value={formatTokenBalance(
            balances.token,
            balances.tokenDecimals,
            balances.tokenSymbol,
          )}
          detail="Used for VM payment stream deposits"
          icon={<RiCopperCoinLine className="h-5 w-5" aria-hidden />}
          tone={balances.token && balances.token > 0n ? "success" : "neutral"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.8fr)]">
        <Card>
          <CardBody className="space-y-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-text-primary">
                  Mint Hoodi tGLM
                </h2>
                <p className="mt-1 text-sm text-text-secondary">
                  The Hoodi tGLM minter sends 1000 tGLM to the connected wallet.
                  Your wallet pays only Hoodi ETH gas for the mint transaction.
                </p>
              </div>
              <Button
                onClick={action}
                busy={busy === "connect" || busy === "mint"}
                disabled={
                  wallet.paymentReady &&
                  (!fundingConfig.minterAddress || !hasNativeGas)
                }
                className="shrink-0"
              >
                <RiCopperCoinLine className="h-4 w-4" aria-hidden />
                {actionLabel}
              </Button>
            </div>

            {txHash ? (
              <Alert tone="success">
                Mint transaction submitted:{" "}
                {txUrl ? (
                  <a
                    className="font-mono underline"
                    href={txUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {shortAddress(txHash)}
                  </a>
                ) : (
                  <span className="font-mono">{shortAddress(txHash)}</span>
                )}
              </Alert>
            ) : null}

            <KeyValueList
              items={[
                {
                  key: "wallet",
                  label: "Recipient",
                  value: (
                    <span className="inline-flex max-w-full min-w-0 items-center justify-end gap-2">
                      <span className="min-w-0 truncate font-mono">
                        {wallet.account || "Connect wallet"}
                      </span>
                      {wallet.account ? (
                        <button
                          type="button"
                          className="text-text-secondary hover:text-primary"
                          onClick={copyAddress}
                          title="Copy wallet address"
                        >
                          <RiFileCopyLine className="h-4 w-4" aria-hidden />
                        </button>
                      ) : null}
                    </span>
                  ),
                },
                {
                  key: "token",
                  label: "tGLM token",
                  value: (
                    <span className="block min-w-0 truncate font-mono">
                      {fundingConfig.tokenAddress || "Not configured"}
                    </span>
                  ),
                },
                {
                  key: "minter",
                  label: "Minter contract",
                  value: (
                    <span className="block min-w-0 truncate font-mono">
                      {fundingConfig.minterAddress || "Not configured"}
                    </span>
                  ),
                },
              ]}
            />
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-text-primary">
                Get Hoodi ETH
              </h2>
              <p className="mt-1 text-sm text-text-secondary">
                Hoodi ETH is the gas token. The PoW faucet asks your browser to
                do mining work, then lets you claim Hoodi ETH to your wallet.
              </p>
            </div>

            <ol className="space-y-3 text-sm text-text-secondary">
              <li className="flex gap-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-semibold text-primary">
                  1
                </span>
                Copy or connect the same wallet address you use here.
              </li>
              <li className="flex gap-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-semibold text-primary">
                  2
                </span>
                Mine in the faucet tab until the claim button becomes available.
              </li>
              <li className="flex gap-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-semibold text-primary">
                  3
                </span>
                Claim Hoodi ETH and return here. Balances update automatically
                when this page regains focus.
              </li>
            </ol>

            <div className="flex flex-col gap-3 sm:flex-row">
              {fundingConfig.faucetUrl ? (
                <a
                  className="btn btn-primary gap-2"
                  href={fundingConfig.faucetUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <RiArrowRightUpLine className="h-4 w-4" aria-hidden />
                  Open PoW faucet
                </a>
              ) : null}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
