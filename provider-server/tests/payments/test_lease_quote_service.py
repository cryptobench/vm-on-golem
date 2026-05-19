import pytest
from eth_account import Account

from provider.errors import ValidationError
from provider.payments.domain import LeaseQuoteCommand
from provider.payments.lease_quote_service import LeaseQuoteService

PRIVATE_KEY = "0x" + "11" * 32
PROVIDER = Account.from_key(PRIVATE_KEY).address
REQUESTOR = "0x3333333333333333333333333333333333333333"
CONTRACT = "0x1111111111111111111111111111111111111111"
TOKEN = "0x4444444444444444444444444444444444444444"
LEASE_ID = "0x" + "aa" * 32


def test_terms_hash_returns_0x_prefixed_bytes32():
    terms_hash = LeaseQuoteService._terms_hash(
        provider_address=PROVIDER,
        requestor_address=REQUESTOR,
        vm_name="test-vm",
        image="24.04",
        cpu=1,
        memory=1,
        storage=10,
        rate_per_second=1,
        duration_seconds=3600,
        contract_address=CONTRACT,
        glm_token_address=TOKEN,
        chain_id=31337,
        lease_id=LEASE_ID,
    )

    assert terms_hash.startswith("0x")
    assert len(bytes.fromhex(terms_hash[2:])) == 32


def test_create_quote_uses_provider_default_image_when_omitted(monkeypatch):
    monkeypatch.setattr(LeaseQuoteService, "_chain_id", lambda *_: 31337)
    service = LeaseQuoteService(
        {
            "PROVIDER_ID": PROVIDER,
            "STREAM_PAYMENT_ADDRESS": CONTRACT,
            "GLM_TOKEN_ADDRESS": TOKEN,
            "ETHEREUM_PRIVATE_KEY": PRIVATE_KEY,
            "PAYMENTS_RPC_URL": "http://rpc.invalid",
            "DEFAULT_VM_IMAGE": "custom-image",
            "PRICE_GLM_PER_CORE_MONTH": "0.000000000002628",
            "PRICE_GLM_PER_GB_RAM_MONTH": "0",
            "PRICE_GLM_PER_GB_STORAGE_MONTH": "0",
        }
    )

    quote = service.create_quote(
        LeaseQuoteCommand(
            vm_name="test-vm",
            cpu=1,
            memory=1,
            storage=10,
            duration_seconds=3600,
            requestor_address=REQUESTOR,
        )
    )

    expected_terms_hash = LeaseQuoteService._terms_hash(
        provider_address=PROVIDER,
        requestor_address=REQUESTOR,
        vm_name="test-vm",
        image="custom-image",
        cpu=1,
        memory=1,
        storage=10,
        rate_per_second=quote.rate_per_second_wei,
        duration_seconds=3600,
        contract_address=CONTRACT,
        glm_token_address=TOKEN,
        chain_id=31337,
        lease_id=quote.lease_id,
    )
    assert quote.terms_hash == expected_terms_hash


def test_sign_quote_accepts_unprefixed_terms_hash_bytes32():
    signature = LeaseQuoteService._sign_quote(
        private_key=PRIVATE_KEY,
        chain_id=31337,
        contract_address=CONTRACT,
        recipient=PROVIDER,
        deposit=3600,
        rate_per_second=1,
        lease_id=LEASE_ID,
        terms_hash="22" * 32,
        quote_expires_at=1_800_000_000,
    )

    assert signature.startswith("0x")


def test_provider_private_key_must_match_provider_id():
    wrong_provider = Account.from_key("0x" + "22" * 32).address

    with pytest.raises(ValidationError, match="private key does not match"):
        LeaseQuoteService._require_provider_private_key_matches(
            PRIVATE_KEY,
            wrong_provider,
        )


@pytest.mark.parametrize("value", ["22" * 31, "not-hex"])
def test_sign_quote_rejects_invalid_terms_hash(value):
    with pytest.raises(ValidationError, match="terms_hash"):
        LeaseQuoteService._sign_quote(
            private_key=PRIVATE_KEY,
            chain_id=31337,
            contract_address=CONTRACT,
            recipient=PROVIDER,
            deposit=3600,
            rate_per_second=1,
            lease_id=LEASE_ID,
            terms_hash=value,
            quote_expires_at=1_800_000_000,
        )
