from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Dict

from web3 import Web3
from eth_account import Account
from golem_streaming_abi import STREAM_PAYMENT_ABI, ERC20_ABI


@dataclass
class StreamPaymentConfig:
    rpc_url: str
    contract_address: str
    glm_token_address: str
    private_key: str


class StreamPaymentClient:
    def __init__(self, cfg: StreamPaymentConfig):
        self.web3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
        self.account = Account.from_key(cfg.private_key)
        self.web3.eth.default_account = self.account.address

        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(cfg.contract_address), abi=STREAM_PAYMENT_ABI
        )
        self.erc20 = self.web3.eth.contract(
            address=Web3.to_checksum_address(cfg.glm_token_address), abi=ERC20_ABI
        )

    def _send(self, fn) -> Dict[str, Any]:
        base = {
            "from": self.account.address,
            "nonce": self.web3.eth.get_transaction_count(self.account.address),
        }
        # Fill chainId
        try:
            base["chainId"] = getattr(self.web3.eth, "chain_id", None) or self.web3.eth.chain_id
        except Exception:
            pass
        # Try gas estimation and fee fields
        try:
            tx_preview = fn.build_transaction(base)
            gas = self.web3.eth.estimate_gas(tx_preview)
            base["gas"] = gas
        except Exception:
            pass
        try:
            # Prefer EIP-1559 if available
            max_fee = getattr(self.web3.eth, "max_priority_fee", None)
            if max_fee is not None:
                base.setdefault("maxPriorityFeePerGas", max_fee)
            base.setdefault("maxFeePerGas", getattr(self.web3.eth, "gas_price", lambda: None)() or self.web3.eth.gas_price)
        except Exception:
            try:
                base.setdefault("gasPrice", self.web3.eth.gas_price)
            except Exception:
                pass

        tx = fn.build_transaction(base)
        # In production, sign and send raw; in tests, Account may be a dummy without signer
        if hasattr(self.account, "sign_transaction"):
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
        else:
            tx_hash = self.web3.eth.send_transaction(tx)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        return {"transactionHash": tx_hash.hex(), "status": receipt.status, "logs": receipt.logs}

    def create_stream(self, provider_address: str, deposit_wei: int, rate_per_second_wei: int) -> int:
        # 1) Approve deposit for the StreamPayment contract (only if needed)
        try:
            allowance = self.erc20.functions.allowance(self.account.address, self.contract.address).call()
        except Exception:
            allowance = 0
        if int(allowance) < int(deposit_wei):
            approve = self.erc20.functions.approve(self.contract.address, int(deposit_wei))
            self._send(approve)

        # 2) Create stream
        fn = self.contract.functions.createStream(
            self.erc20.address,
            Web3.to_checksum_address(provider_address),
            int(deposit_wei),
            int(rate_per_second_wei),
        )
        receipt = self._send(fn)

        # Try to parse StreamCreated event for streamId
        try:
            for log in receipt["logs"]:
                # very naive filter: topic0 = keccak256(StreamCreated(...))
                # When ABI is attached to contract, use contract.events
                ev = self.contract.events.StreamCreated().process_log(log)
                return int(ev["args"]["streamId"])
        except Exception:
            pass
        # As a fallback, cannot easily fetch return value from a tx; caller should query later
        raise RuntimeError("create_stream: could not parse streamId from receipt")

    def withdraw(self, stream_id: int) -> str:
        fn = self.contract.functions.withdraw(int(stream_id))
        receipt = self._send(fn)
        return receipt["transactionHash"]

    def terminate(self, stream_id: int) -> str:
        fn = self.contract.functions.terminate(int(stream_id))
        receipt = self._send(fn)
        return receipt["transactionHash"]

    def top_up(self, stream_id: int, amount_wei: int) -> str:
        # Approve first (only if needed)
        try:
            allowance = self.erc20.functions.allowance(self.account.address, self.contract.address).call()
        except Exception:
            allowance = 0
        if int(allowance) < int(amount_wei):
            approve = self.erc20.functions.approve(self.contract.address, int(amount_wei))
            self._send(approve)
        # Top up
        fn = self.contract.functions.topUp(int(stream_id), int(amount_wei))
        receipt = self._send(fn)
        return receipt["transactionHash"]
