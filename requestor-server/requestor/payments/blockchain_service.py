from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from eth_account import Account
from golem_streaming_abi import ERC20_ABI, STREAM_PAYMENT_ABI
from web3 import Web3

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
logger = logging.getLogger(__name__)


def _bytes32_hex(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "hex"):
        raw = value.hex()
        return raw if raw.startswith("0x") else f"0x{raw}"
    raw = str(value)
    return raw if raw.startswith("0x") else f"0x{raw}"


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def parse_stream_tuple(value: Any) -> dict[str, Any]:
    """Normalize known StreamPayment stream tuple shapes.

    The current contract returns 10 fields including token. Some deployed
    transitional contracts return the same stream data without token.
    Older local/test contracts returned a halted flag instead of lease fields.
    """
    values = tuple(value)
    token = None
    halted = False
    lease_id = None
    terms_hash = None

    if len(values) == 10:
        (
            token,
            sender,
            recipient,
            start_time,
            stop_time,
            rate_per_second,
            deposit,
            withdrawn,
            lease_id,
            terms_hash,
        ) = values
    elif len(values) == 9:
        if _is_int_like(values[2]):
            (
                sender,
                recipient,
                start_time,
                stop_time,
                rate_per_second,
                deposit,
                withdrawn,
                lease_id,
                terms_hash,
            ) = values
        else:
            (
                token,
                sender,
                recipient,
                start_time,
                stop_time,
                rate_per_second,
                deposit,
                withdrawn,
                halted,
            ) = values
    elif len(values) == 8:
        (
            sender,
            recipient,
            start_time,
            stop_time,
            rate_per_second,
            deposit,
            withdrawn,
            halted,
        ) = values
    else:
        raise ValueError(f"unexpected stream tuple length: {len(values)}")

    return {
        "token": token,
        "sender": sender,
        "recipient": recipient,
        "startTime": int(start_time),
        "stopTime": int(stop_time),
        "ratePerSecond": int(rate_per_second),
        "deposit": int(deposit),
        "withdrawn": int(withdrawn),
        "leaseId": _bytes32_hex(lease_id),
        "termsHash": _bytes32_hex(terms_hash),
        "halted": bool(halted),
    }


@dataclass
class StreamPaymentConfig:
    rpc_url: str
    contract_address: str
    # GLM ERC20 token used by StreamPayment.
    glm_token_address: str
    private_key: str


class StreamPaymentClient:
    def __init__(self, cfg: StreamPaymentConfig):
        self.web3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
        self.account = Account.from_key(cfg.private_key)
        self.web3.eth.default_account = self.account.address

        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(cfg.contract_address),
            abi=STREAM_PAYMENT_ABI,
        )
        token_address = Web3.to_checksum_address(cfg.glm_token_address)
        if token_address.lower() == Web3.to_checksum_address(ZERO_ADDRESS).lower():
            raise ValueError("GLM_TOKEN_ADDRESS is required for GLM payments")
        self.token_address = token_address
        self.erc20 = self.web3.eth.contract(address=self.token_address, abi=ERC20_ABI)

    def _eth_value(self, name: str) -> Any:
        value = getattr(self.web3.eth, name)
        return value() if callable(value) else value

    def _set_chain_id(self, base: dict[str, Any]) -> None:
        try:
            chain_id = self._eth_value("chain_id")
        except Exception:
            logger.debug("Could not determine chain id", exc_info=True)
            return
        if chain_id is not None:
            base["chainId"] = chain_id

    def _set_gas_limit(self, fn, base: dict[str, Any]) -> None:
        try:
            tx_preview = fn.build_transaction(base)
            base["gas"] = self.web3.eth.estimate_gas(tx_preview)
        except Exception:
            logger.debug("Could not estimate gas for transaction", exc_info=True)

    def _set_fee_fields(self, base: dict[str, Any]) -> None:
        has_legacy = "gasPrice" in base
        has_eip1559 = "maxFeePerGas" in base or "maxPriorityFeePerGas" in base
        if has_legacy and has_eip1559:
            raise ValueError(
                "Transaction fee fields cannot mix gasPrice with EIP-1559 fees"
            )
        if has_legacy or has_eip1559:
            return

        try:
            priority_fee = self._eth_value("max_priority_fee")
            gas_price = self._eth_value("gas_price")
        except Exception:
            logger.debug("Could not read EIP-1559 fee fields", exc_info=True)
        else:
            if priority_fee is not None and gas_price is not None:
                base["maxPriorityFeePerGas"] = int(priority_fee)
                base["maxFeePerGas"] = max(int(gas_price), int(priority_fee))
                return

        try:
            gas_price = self._eth_value("gas_price")
        except Exception:
            logger.debug("Could not read legacy gas price", exc_info=True)
            return
        if gas_price is not None:
            base["gasPrice"] = int(gas_price)

    def _send(self, fn, extra: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
        base = {
            "from": self.account.address,
            "nonce": self.web3.eth.get_transaction_count(self.account.address),
        }
        if extra:
            base.update(extra)
        self._set_chain_id(base)
        self._set_gas_limit(fn, base)
        self._set_fee_fields(base)

        tx = fn.build_transaction(base)
        # In production, sign and send raw; in tests, Account may be a dummy without signer
        if hasattr(self.account, "sign_transaction"):
            signed = self.account.sign_transaction(tx)
            raw = getattr(signed, "rawTransaction", None) or getattr(
                signed, "raw_transaction", None
            )
            if raw is None:
                raise RuntimeError(
                    "sign_transaction did not return raw transaction bytes"
                )
            tx_hash = self.web3.eth.send_raw_transaction(raw)
        else:
            tx_hash = self.web3.eth.send_transaction(tx)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        return {
            "transactionHash": tx_hash.hex(),
            "status": receipt.status,
            "logs": receipt.logs,
        }

    def create_stream(
        self,
        provider_address: str,
        deposit_wei: int,
        rate_per_second_wei: int,
        lease_id: str,
        terms_hash: str,
        quote_expires_at: int,
        provider_signature: str,
    ) -> int:
        self._approve_if_needed(int(deposit_wei))
        fn = self.contract.functions.createStream(
            Web3.to_checksum_address(provider_address),
            int(deposit_wei),
            int(rate_per_second_wei),
            lease_id,
            terms_hash,
            int(quote_expires_at),
            provider_signature,
        )
        tx_receipt = self._send(fn)

        # Try to parse StreamCreated event for streamId
        try:
            for log in tx_receipt["logs"]:
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
        self._approve_if_needed(int(amount_wei))
        fn = self.contract.functions.topUp(int(stream_id), int(amount_wei))
        receipt = self._send(fn)
        return receipt["transactionHash"]

    def _approve_if_needed(self, amount_wei: int) -> None:
        try:
            allowance = self.erc20.functions.allowance(
                self.account.address, self.contract.address
            ).call()
        except Exception:
            logger.warning(
                "Could not read GLM allowance; forcing approval transaction",
                exc_info=True,
            )
            allowance = 0
        if int(allowance) >= int(amount_wei):
            return
        approve = self.erc20.functions.approve(self.contract.address, int(amount_wei))
        self._send(approve)
