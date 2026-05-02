"use client";
import React from "react";
import {
  getPaymentNetworkErrorMessage,
  getPaymentsChain,
  isExpectedPaymentsChain,
  PaymentNetworkError,
  readWalletChainId,
  switchToPaymentsNetwork,
  toPaymentNetworkError,
  type PaymentsChain,
} from "../lib/chain";

export type WalletNetworkStatus =
  | "not_installed"
  | "disconnected"
  | "wrong_network"
  | "rpc_error"
  | "switching"
  | "ready";

type WalletState = {
  isInstalled: boolean;
  isConnected: boolean;
  account: string | null;
  chainId: string | null;
  networkStatus: WalletNetworkStatus;
  networkError: string | null;
};

type WalletContextValue = WalletState & {
  expectedChain: PaymentsChain;
  isCorrectNetwork: boolean;
  paymentReady: boolean;
  paymentMessage: string | null;
  connect: () => Promise<void>;
  refresh: () => Promise<void>;
  switchToPaymentsNetwork: () => Promise<void>;
  ensurePaymentsNetwork: () => Promise<void>;
};

const defaultChain = getPaymentsChain({});

const WalletContext = React.createContext<WalletContextValue>({
  isInstalled: false,
  isConnected: false,
  account: null,
  chainId: null,
  networkStatus: "not_installed",
  networkError: null,
  expectedChain: defaultChain,
  isCorrectNetwork: false,
  paymentReady: false,
  paymentMessage: "Connect MetaMask before using payment streams.",
  connect: async () => {},
  refresh: async () => {},
  switchToPaymentsNetwork: async () => {},
  ensurePaymentsNetwork: async () => {},
});

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [settingsVersion, setSettingsVersion] = React.useState(0);
  const expectedChain = React.useMemo(
    () => getPaymentsChain(),
    [settingsVersion],
  );
  const [state, setState] = React.useState<WalletState>({
    isInstalled: false,
    isConnected: false,
    account: null,
    chainId: null,
    networkStatus: "not_installed",
    networkError: null,
  });

  const syncFromEth = React.useCallback(async () => {
    if (typeof window === "undefined") return;
    const { ethereum } = window as any;
    if (!ethereum?.request) {
      setState({
        isInstalled: false,
        isConnected: false,
        account: null,
        chainId: null,
        networkStatus: "not_installed",
        networkError: null,
      });
      return;
    }

    const accounts: string[] = await ethereum
      .request({ method: "eth_accounts" })
      .catch(() => []);
    const connected = Array.isArray(accounts) && accounts.length > 0;

    let chainId: string | null = null;
    let networkStatus: WalletNetworkStatus = connected ? "wrong_network" : "disconnected";
    let networkError: string | null = null;
    try {
      chainId = await readWalletChainId(ethereum);
      if (!connected) {
        networkStatus = "disconnected";
      } else if (isExpectedPaymentsChain(chainId, expectedChain)) {
        networkStatus = "ready";
      } else {
        networkStatus = "wrong_network";
      }
    } catch (error) {
      networkStatus = connected ? "rpc_error" : "disconnected";
      networkError = connected ? getPaymentNetworkErrorMessage(error, expectedChain) : null;
    }

    setState({
      isInstalled: true,
      isConnected: connected,
      account: accounts?.[0] || null,
      chainId,
      networkStatus,
      networkError,
    });
  }, [expectedChain]);

  React.useEffect(() => {
    syncFromEth();
    if (typeof window === "undefined") return;
    const onSettings = () => setSettingsVersion((version) => version + 1);
    window.addEventListener("requestor_settings_changed", onSettings as EventListener);
    window.addEventListener("storage", onSettings);
    return () => {
      window.removeEventListener("requestor_settings_changed", onSettings as EventListener);
      window.removeEventListener("storage", onSettings);
    };
  }, [syncFromEth]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const { ethereum } = window as any;
    if (!ethereum?.on) return;
    const onAccounts = () => syncFromEth();
    const onChain = () => syncFromEth();
    ethereum.on("accountsChanged", onAccounts);
    ethereum.on("chainChanged", onChain);
    return () => {
      ethereum.removeListener?.("accountsChanged", onAccounts);
      ethereum.removeListener?.("chainChanged", onChain);
    };
  }, [syncFromEth]);

  const switchWallet = React.useCallback(async () => {
    if (typeof window === "undefined") return;
    const { ethereum } = window as any;
    setState((current) => ({
      ...current,
      networkStatus: "switching",
      networkError: null,
    }));
    try {
      await switchToPaymentsNetwork(ethereum, expectedChain);
      await syncFromEth();
    } catch (error) {
      const paymentError = toPaymentNetworkError(error);
      setState((current) => ({
        ...current,
        networkStatus: paymentError?.code === "rpc_unhealthy" ? "rpc_error" : "wrong_network",
        networkError: getPaymentNetworkErrorMessage(error, expectedChain),
      }));
      throw error;
    }
  }, [expectedChain, syncFromEth]);

  const connect = React.useCallback(async () => {
    if (typeof window === "undefined") return;
    const { ethereum } = window as any;
    if (!ethereum?.request) {
      const error = new PaymentNetworkError(
        "missing_wallet",
        "MetaMask is required for payment streams.",
      );
      setState((current) => ({
        ...current,
        isInstalled: false,
        networkStatus: "not_installed",
        networkError: error.message,
      }));
      throw error;
    }
    try {
      await ethereum.request({ method: "eth_requestAccounts" });
      await switchWallet();
    } catch (error) {
      await syncFromEth();
      setState((current) => ({
        ...current,
        networkError: getPaymentNetworkErrorMessage(error, expectedChain),
      }));
      throw error;
    }
  }, [expectedChain, switchWallet, syncFromEth]);

  const ensurePaymentsNetwork = React.useCallback(async () => {
    if (!state.isInstalled) {
      throw new PaymentNetworkError(
        "missing_wallet",
        "MetaMask is required for payment streams.",
      );
    }
    if (state.networkStatus === "ready") return;
    if (!state.isConnected) {
      await connect();
      return;
    }
    await switchWallet();
  }, [connect, state.isConnected, state.networkStatus, switchWallet]);

  const isCorrectNetwork = state.networkStatus === "ready";
  const paymentReady = state.isInstalled && state.isConnected && isCorrectNetwork;
  const paymentMessage = !state.isInstalled
    ? "MetaMask is required for payment streams."
    : !state.isConnected
      ? "Connect MetaMask before using payment streams."
      : !isCorrectNetwork
        ? (state.networkError || `Switch MetaMask to ${expectedChain.chainName} before using payment streams.`)
        : null;

  const value = React.useMemo<WalletContextValue>(
    () => ({
      ...state,
      expectedChain,
      isCorrectNetwork,
      paymentReady,
      paymentMessage,
      connect,
      refresh: syncFromEth,
      switchToPaymentsNetwork: switchWallet,
      ensurePaymentsNetwork,
    }),
    [
      state,
      expectedChain,
      isCorrectNetwork,
      paymentReady,
      paymentMessage,
      connect,
      syncFromEth,
      switchWallet,
      ensurePaymentsNetwork,
    ],
  );

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
}

export function useWallet() {
  return React.useContext(WalletContext);
}
