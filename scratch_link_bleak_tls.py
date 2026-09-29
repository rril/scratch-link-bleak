"""Generate a standalone, locally trusted TLS certificate for Scratch Link Bleak.

The generated certificate is a *server leaf*, NOT a certificate authority.
Trust it as a peer ("P,,") in Chrome's NSS database. Nothing is
automatically installed into the browser or system trust store.
"""
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

HOSTNAME = "device-manager.scratch.mit.edu"
CERT_DIR = Path.home() / ".local" / "share" / "scratch-link-bleak"
CERT_FILE = CERT_DIR / "server.crt"
KEY_FILE = CERT_DIR / "server.key"


def generate_certificate():
    """Return (cert_path, key_path), creating files without replacing existing ones."""
    if CERT_FILE.exists() or KEY_FILE.exists():
        if CERT_FILE.is_file() and KEY_FILE.is_file():
            raise FileExistsError(
                f"TLS files already exist in {CERT_DIR}; refusing to overwrite them."
            )
        raise FileExistsError(
            f"Partial TLS setup in {CERT_DIR}; inspect it before running setup again."
        )

    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, HOSTNAME),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Scratch Link Bleak local only"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(HOSTNAME)]), critical=False
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    key_bytes = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()
    )
    cert_bytes = cert.public_bytes(serialization.Encoding.PEM)

    CERT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    CERT_DIR.chmod(0o700)
    # O_EXCL guarantees we never silently overwrite a real user's key.
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(key_bytes)
        fd = os.open(CERT_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as f:
            f.write(cert_bytes)
    except BaseException:
        # A failed setup must not leave a mismatched key and certificate pair.
        KEY_FILE.unlink(missing_ok=True)
        raise
    KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return CERT_FILE, KEY_FILE
