import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def load_or_create_rsa_key(path: Path, mode: int = 0o600) -> rsa.RSAPrivateKey:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    path.chmod(mode)
    return key


def cert_is_valid_for_ip(
    cert_path: Path,
    key_path: Path,
    ip_address: str,
    renew_before_hours: int,
) -> tuple[bool, str]:
    if not cert_path.exists() or not key_path.exists():
        return False, "missing certificate"
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        cert_public = cert.public_key().public_numbers()
        key_public = key.public_key().public_numbers()
        if cert_public != key_public:
            return False, "certificate key does not match"
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        ip = ipaddress.ip_address(ip_address)
        if ip not in san.get_values_for_type(x509.IPAddress):
            return False, "certificate does not match public IP"
        expires = cert.not_valid_after.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc) + timedelta(hours=renew_before_hours):
            return False, "certificate renewal required"
        return True, f"valid {max(1, (expires - datetime.now(timezone.utc)).days)} days"
    except Exception as exc:
        return False, str(exc)


def build_ip_csr(private_key: rsa.RSAPrivateKey, ip_address: str) -> bytes:
    ip = ipaddress.ip_address(ip_address)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([]))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip)]), False)
        .sign(private_key, hashes.SHA256())
    )
    return csr.public_bytes(serialization.Encoding.DER)
