from eth_account import Account

import pytest

from provider.errors import ValidationError
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
