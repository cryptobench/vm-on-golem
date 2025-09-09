from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from web3 import Web3
from eth_account import Account
from golem_streaming_abi import STREAM_PAYMENT_ABI


 # ABI imported from shared package


@dataclass
class StreamPaymentConfig:
    rpc_url: str
    contract_address: str
    private_key: str


class StreamPaymentClient:
    def __init__(self, cfg: StreamPaymentConfig):
        self.web3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
        self.account = Account.from_key(cfg.private_key)
        self.web3.eth.default_account = self.account.address
        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(cfg.contract_address), abi=STREAM_PAYMENT_ABI
        )

    def _send(self, fn) -> Dict[str, Any]:
        tx = fn.build_transaction(
            {
                "from": self.account.address,
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
            }
        )
        if hasattr(self.account, "sign_transaction"):
            signed = self.account.sign_transaction(tx)
            raw = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction", None)
            if raw is None:
                raise RuntimeError("sign_transaction did not return raw transaction bytes")
            tx_hash = self.web3.eth.send_raw_transaction(raw)
        else:
            tx_hash = self.web3.eth.send_transaction(tx)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        return {"transactionHash": tx_hash.hex(), "status": receipt.status}

    def withdraw(self, stream_id: int) -> str:
        fn = self.contract.functions.withdraw(int(stream_id))
        receipt = self._send(fn)
        return receipt["transactionHash"]
    def terminate(self, stream_id: int) -> str:
        fn = self.contract.functions.terminate(int(stream_id))
        receipt = self._send(fn)
        return receipt["transactionHash"]

class StreamPaymentReader:
    def __init__(self, rpc_url: str, contract_address: str):
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=STREAM_PAYMENT_ABI
        )

    def get_stream(self, stream_id: int) -> dict:
        token, sender, recipient, startTime, stopTime, ratePerSecond, deposit, withdrawn, halted = (
            self.contract.functions.streams(int(stream_id)).call()
        )
        return {
            "token": token,
            "sender": sender,
            "recipient": recipient,
            "startTime": int(startTime),
            "stopTime": int(stopTime),
            "ratePerSecond": int(ratePerSecond),
            "deposit": int(deposit),
            "withdrawn": int(withdrawn),
            "halted": bool(halted),
        }

    def verify_stream(self, stream_id: int, expected_recipient: str) -> tuple[bool, str]:
        try:
            s = self.get_stream(stream_id)
        except Exception as e:
            return False, f"stream lookup failed: {e}"
        if s["recipient"].lower() != expected_recipient.lower():
            return False, "recipient mismatch"
        if s["deposit"] <= 0:
            return False, "no deposit"
        now = int(self.web3.eth.get_block("latest")["timestamp"])
        if s["startTime"] > now:
            return False, "stream not started"
        if s["halted"]:
            return False, "stream halted"
        return True, "ok"

    # Reader should remain read-only; no terminate here
