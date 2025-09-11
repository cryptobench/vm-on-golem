"use client";
import React from "react";

type WalletState = {
  isInstalled: boolean;
  isConnected: boolean;
  account: string | null;
  chainId: string | null; // hex string like 0x1
};

type WalletContextValue = WalletState & {
  connect: () => Promise<void>;
};

const WalletContext = React.createContext<WalletContextValue>({
  isInstalled: false,
  isConnected: false,
  account: null,
  chainId: null,
  connect: async () => {},
});

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<WalletState>({
    isInstalled: false,
    isConnected: false,
    account: null,
    chainId: null,
  });

  const syncFromEth = async (ethereum: any) => {
    try {
      const [accounts, chainId] = await Promise.all([
        ethereum.request({ method: "eth_accounts" }).catch(() => []),
        ethereum.request({ method: "eth_chainId" }).catch(() => null),
      ]);
      setState(s => ({
        ...s,
        isInstalled: true,
        isConnected: Array.isArray(accounts) && accounts.length > 0,
        account: accounts?.[0] || null,
        chainId: chainId || null,
      }));
    } catch {
      setState(s => ({ ...s, isInstalled: true }));
    }
  };

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const { ethereum } = window as any;
    if (!ethereum) {
      setState({ isInstalled: false, isConnected: false, account: null, chainId: null });
      return;
    }
    setState(s => ({ ...s, isInstalled: true }));
    syncFromEth(ethereum);
    const onAccounts = (accs: string[]) => setState(s => ({ ...s, isConnected: !!(accs && accs.length), account: accs?.[0] || null }));
    const onChain = (cid: string) => setState(s => ({ ...s, chainId: cid }));
    ethereum.on?.("accountsChanged", onAccounts);
    ethereum.on?.("chainChanged", onChain);
    return () => {
      ethereum.removeListener?.("accountsChanged", onAccounts);
      ethereum.removeListener?.("chainChanged", onChain);
    };
  }, []);

  const connect = React.useCallback(async () => {
    if (typeof window === "undefined") return;
    const { ethereum } = window as any;
    if (!ethereum) {
      alert("MetaMask not detected");
      return;
    }
    try {
      const accounts: string[] = await ethereum.request({ method: "eth_requestAccounts" });
      const chainId: string = await ethereum.request({ method: "eth_chainId" });
      setState({ isInstalled: true, isConnected: accounts.length > 0, account: accounts?.[0] || null, chainId: chainId || null });
    } catch (e) {
      // user rejected or other error; leave state as-is
    }
  }, []);

  const value = React.useMemo<WalletContextValue>(() => ({ ...state, connect }), [state, connect]);

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
}

export function useWallet() {
  return React.useContext(WalletContext);
}

