import secrets
import time
from decimal import Decimal, ROUND_CEILING
from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

from provider.errors import ExternalServiceError, ValidationError
from provider.utils.logging import setup_logger
from provider.vm.models import VMResources

from .domain import LeaseQuote, LeaseQuoteCommand


SECONDS_PER_MONTH = Decimal("730") * Decimal("3600")
QUOTE_TTL_SECONDS = 900
logger = setup_logger(__name__)


class LeaseQuoteService:
    """Creates provider-authoritative, provider-signed V2 lease quotes."""

    def __init__(self, settings: Any):
        self.settings = settings

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    def create_quote(self, command: LeaseQuoteCommand) -> LeaseQuote:
        if command.duration_seconds <= 0:
            raise ValidationError("duration_seconds must be positive")

        provider_address = str(self._setting("PROVIDER_ID", "") or "")
        contract_address = str(self._setting("STREAM_PAYMENT_ADDRESS", "") or "")
        glm_token_address = str(self._setting("GLM_TOKEN_ADDRESS", "") or "")
        private_key = str(self._setting("ETHEREUM_PRIVATE_KEY", "") or "")
        rpc_url = str(self._setting("POLYGON_RPC_URL", "") or "")
        if not all(
            [
                provider_address,
                contract_address,
                glm_token_address,
                private_key,
                rpc_url,
            ]
        ):
            raise ValidationError("provider payment settings are incomplete")

        chain_id = self._chain_id(rpc_url)
        rate = self._rate_per_second_wei(
            VMResources(
                cpu=command.cpu,
                memory=command.memory,
                storage=command.storage,
            )
        )
        min_deposit = int(rate) * int(command.duration_seconds)
        lease_id = "0x" + secrets.token_hex(32)
        terms_hash = self._terms_hash(
            provider_address=provider_address,
            requestor_address=command.requestor_address,
            vm_name=command.vm_name,
            image=command.image or "",
            cpu=command.cpu,
            memory=command.memory,
            storage=command.storage,
            rate_per_second=rate,
            duration_seconds=command.duration_seconds,
            contract_address=contract_address,
            glm_token_address=glm_token_address,
            chain_id=chain_id,
            lease_id=lease_id,
        )
        quote_expires_at = int(time.time()) + QUOTE_TTL_SECONDS
        signature = self._sign_quote(
            private_key=private_key,
            chain_id=chain_id,
            contract_address=contract_address,
            recipient=provider_address,
            deposit=min_deposit,
            rate_per_second=rate,
            lease_id=lease_id,
            terms_hash=terms_hash,
            quote_expires_at=quote_expires_at,
        )
        return LeaseQuote(
            provider_address=provider_address,
            chain_id=chain_id,
            contract_address=contract_address,
            glm_token_address=glm_token_address,
            lease_id=lease_id,
            terms_hash=terms_hash,
            rate_per_second_wei=rate,
            min_deposit_wei=min_deposit,
            min_runway_seconds=command.duration_seconds,
            quote_expires_at=quote_expires_at,
            signature=signature,
        )

    def _chain_id(self, rpc_url: str) -> int:
        try:
            return int(Web3(Web3.HTTPProvider(rpc_url)).eth.chain_id)
        except Exception as exc:
            logger.error(
                "Failed to read payments chain id for lease quote",
                extra={"rpc_url": rpc_url},
                exc_info=True,
            )
            raise ExternalServiceError(
                "payments chain RPC is unavailable while creating lease quote"
            ) from exc

    def _rate_per_second_wei(self, resources: VMResources) -> int:
        glm_month = (
            Decimal(str(self._setting("PRICE_GLM_PER_CORE_MONTH", 0))) * resources.cpu
            + Decimal(str(self._setting("PRICE_GLM_PER_GB_RAM_MONTH", 0)))
            * resources.memory
            + Decimal(str(self._setting("PRICE_GLM_PER_GB_STORAGE_MONTH", 0)))
            * resources.storage
        )
        if glm_month <= 0:
            from provider.utils.pricing import fetch_glm_usd_price

            glm_usd = fetch_glm_usd_price()
            if glm_usd is None or Decimal(str(glm_usd)) <= 0:
                raise ValidationError("GLM pricing is unavailable")
            usd_month = (
                Decimal(str(self._setting("PRICE_USD_PER_CORE_MONTH", 0)))
                * resources.cpu
                + Decimal(str(self._setting("PRICE_USD_PER_GB_RAM_MONTH", 0)))
                * resources.memory
                + Decimal(str(self._setting("PRICE_USD_PER_GB_STORAGE_MONTH", 0)))
                * resources.storage
            )
            glm_month = usd_month / Decimal(str(glm_usd))
        rate = (glm_month * (Decimal(10) ** 18) / SECONDS_PER_MONTH).to_integral_value(
            rounding=ROUND_CEILING
        )
        if rate <= 0:
            raise ValidationError("computed lease rate is zero")
        return int(rate)

    @staticmethod
    def _terms_hash(
        *,
        provider_address: str,
        requestor_address: str,
        vm_name: str,
        image: str,
        cpu: int,
        memory: int,
        storage: int,
        rate_per_second: int,
        duration_seconds: int,
        contract_address: str,
        glm_token_address: str,
        chain_id: int,
        lease_id: str,
    ) -> str:
        terms_hash = Web3.solidity_keccak(
            [
                "string",
                "address",
                "address",
                "string",
                "string",
                "uint256",
                "uint256",
                "uint256",
                "uint256",
                "uint256",
                "address",
                "address",
                "uint256",
                "bytes32",
            ],
            [
                "golem-vm-lease-v2",
                Web3.to_checksum_address(provider_address),
                Web3.to_checksum_address(requestor_address),
                vm_name,
                image,
                int(cpu),
                int(memory),
                int(storage),
                int(rate_per_second),
                int(duration_seconds),
                Web3.to_checksum_address(contract_address),
                Web3.to_checksum_address(glm_token_address),
                int(chain_id),
                lease_id,
            ],
        ).hex()
        return LeaseQuoteService._bytes32_hex(terms_hash, "terms_hash")

    @staticmethod
    def _bytes32_hex(value: str, field_name: str) -> str:
        raw = value.strip()
        if raw.startswith(("0x", "0X")):
            raw = raw[2:]
        try:
            data = bytes.fromhex(raw)
        except ValueError as exc:
            raise ValidationError(f"{field_name} must be a bytes32 hex value") from exc
        if len(data) != 32:
            raise ValidationError(f"{field_name} must be exactly 32 bytes")
        return "0x" + data.hex()

    @staticmethod
    def _sign_quote(
        *,
        private_key: str,
        chain_id: int,
        contract_address: str,
        recipient: str,
        deposit: int,
        rate_per_second: int,
        lease_id: str,
        terms_hash: str,
        quote_expires_at: int,
    ) -> str:
        lease_id = LeaseQuoteService._bytes32_hex(lease_id, "lease_id")
        terms_hash = LeaseQuoteService._bytes32_hex(terms_hash, "terms_hash")
        message = encode_typed_data(
            domain_data={
                "name": "GolemStreamPayment",
                "version": "2",
                "chainId": int(chain_id),
                "verifyingContract": Web3.to_checksum_address(contract_address),
            },
            message_types={
                "LeaseQuote": [
                    {"name": "recipient", "type": "address"},
                    {"name": "deposit", "type": "uint256"},
                    {"name": "ratePerSecond", "type": "uint128"},
                    {"name": "leaseId", "type": "bytes32"},
                    {"name": "termsHash", "type": "bytes32"},
                    {"name": "quoteExpiresAt", "type": "uint128"},
                ]
            },
            message_data={
                "recipient": Web3.to_checksum_address(recipient),
                "deposit": int(deposit),
                "ratePerSecond": int(rate_per_second),
                "leaseId": lease_id,
                "termsHash": terms_hash,
                "quoteExpiresAt": int(quote_expires_at),
            },
        )
        signature = Account.sign_message(
            message, private_key=private_key
        ).signature.hex()
        return signature if signature.startswith("0x") else f"0x{signature}"
