from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.errors import (
    VMError,
    ProviderError,
    DiscoveryError,
    SSHError,
    ConfigError,
    DatabaseError,
    RequestorError,
)


def test_vm_error_vm_id():
    err = VMError("oops", vm_id="123")
    assert err.vm_id == "123"
    assert str(err) == "oops"


def test_provider_error_is_requestor_error():
    err = ProviderError("p")
    assert isinstance(err, RequestorError)
    assert str(err) == "p"


def test_discovery_error_is_requestor_error():
    err = DiscoveryError("d")
    assert isinstance(err, RequestorError)


def test_ssh_error_is_requestor_error():
    err = SSHError("s")
    assert isinstance(err, RequestorError)


def test_config_error_is_requestor_error():
    err = ConfigError("c")
    assert isinstance(err, RequestorError)


def test_database_error_is_requestor_error():
    err = DatabaseError("db")
    assert isinstance(err, RequestorError)


def test_vm_error_no_id():
    err = VMError("oops")
    assert err.vm_id is None
