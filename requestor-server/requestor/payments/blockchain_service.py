from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Dict

from web3 import Web3
from eth_account import Account


STREAM_PAYMENT_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "deposit", "type": "uint256"},
            {"internalType": "uint128", "name": "ratePerSecond", "type": "uint128"},
        ],
        "name": "createStream",
        "outputs": [{"internalType": "uint256", "name": "streamId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "streamId", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "streamId", "type": "uint256"}],
        "name": "terminate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "streamId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "recipient", "type": "address"},
            {"indexed": False, "internalType": "address", "name": "token", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "deposit", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "ratePerSecond", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "startTime", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "stopTime", "type": "uint256"},
        ],
        "name": "StreamCreated",
        "type": "event",
    },
]

ERC20_ABI = [
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    }
]


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
        tx = fn.build_transaction(
            {
                "from": self.account.address,
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
            }
        )
        # In production, sign and send raw; in tests, Account may be a dummy without signer
        if hasattr(self.account, "sign_transaction"):
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
        else:
            tx_hash = self.web3.eth.send_transaction(tx)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        return {"transactionHash": tx_hash.hex(), "status": receipt.status, "logs": receipt.logs}

    def create_stream(self, provider_address: str, deposit_wei: int, rate_per_second_wei: int) -> int:
        # 1) Approve deposit for the StreamPayment contract
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
        # Approve first
        approve = self.erc20.functions.approve(self.contract.address, int(amount_wei))
        self._send(approve)
        # Top up
        fn = self.contract.functions.topUp(int(stream_id), int(amount_wei))
        receipt = self._send(fn)
        return receipt["transactionHash"]
