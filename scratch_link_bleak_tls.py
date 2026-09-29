"""Create, inspect and safely renew a local (non-CA) TLS server certificate.

The browser trusts this certificate as a *specific server peer*. Renewal therefore
requires importing the NEW public certificate into the browser's certificate store.
No private key is ever copied into that store.
"""
import os
import shutil
import stat
import ssl
import tempfile
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
RENEW_BEFORE = timedelta(days=30)


def _create_pair():
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
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption()),
    )


def _write_exclusive(path, data, mode):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as file:
        file.write(data)
    path.chmod(mode)


def read_certificate(cert_file=None):
    path = Path(cert_file) if cert_file is not None else CERT_FILE
    return x509.load_pem_x509_certificate(path.read_bytes())


def days_remaining(cert_file=None, now=None):
    cert = read_certificate(cert_file)
    expires = getattr(cert, "not_valid_after_utc", None)
    if expires is None:  # cryptography on older Python environments
        expires = cert.not_valid_after.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (expires - now).total_seconds() / 86400


def certificate_fingerprint(cert_file=None):
    return read_certificate(cert_file).fingerprint(hashes.SHA256()).hex().upper()


def validate_pair(cert_path=None, key_path=None):
    cert_path = Path(cert_path) if cert_path is not None else CERT_FILE
    key_path = Path(key_path) if key_path is not None else KEY_FILE
    cert = read_certificate(cert_path)
    if HOSTNAME not in cert.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value.get_values_for_type(x509.DNSName):
        raise ValueError("TLS certificate does not cover the Scratch hostname")
    if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise ValueError("Local TLS server must not be a CA")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    return cert


def generate_certificate():
    """Create once; never overwrite even one existing TLS file."""
    if CERT_FILE.exists() or KEY_FILE.exists():
        if CERT_FILE.is_file() and KEY_FILE.is_file():
            raise FileExistsError(f"TLS files already exist in {CERT_DIR}; refusing to overwrite them.")
        raise FileExistsError(f"Partial TLS setup in {CERT_DIR}; inspect before running setup again.")

    cert_bytes, key_bytes = _create_pair()
    CERT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    CERT_DIR.chmod(0o700)
    try:
        _write_exclusive(KEY_FILE, key_bytes, 0o600)
        _write_exclusive(CERT_FILE, cert_bytes, 0o644)
        validate_pair()
    except BaseException:
        CERT_FILE.unlink(missing_ok=True)
        KEY_FILE.unlink(missing_ok=True)
        raise
    return CERT_FILE, KEY_FILE


def renew_certificate(*, force=False, now=None):
    """Replace cert/key together and preserve recoverable copies in a private backup directory.

    The caller MUST reconfigure browser trust afterward. This function does not
    modify the browser's NSS database.
    """
    validate_pair()
    now = now or datetime.now(timezone.utc)
    remaining = days_remaining(now=now)
    if remaining > RENEW_BEFORE.total_seconds() / 86400 and not force:
        raise ValueError(f"Certificate still has {remaining:.0f} days; renewal is not due yet.")

    cert_bytes, key_bytes = _create_pair()
    backup_root = CERT_DIR / "backups"
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup_root.chmod(0o700)
    backup = backup_root / now.strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(mode=0o700)

    # Private temporary directory on the SAME filesystem, allowing os.replace().
    with tempfile.TemporaryDirectory(prefix=".new-tls-", dir=str(CERT_DIR)) as temporary:
        temp = Path(temporary)
        new_cert, new_key = temp / "server.crt", temp / "server.key"
        _write_exclusive(new_key, key_bytes, 0o600)
        _write_exclusive(new_cert, cert_bytes, 0o644)
        validate_pair(new_cert, new_key)

        # Copy, rather than move, old files first so they remain valid until replacement.
        shutil.copy2(CERT_FILE, backup / "server.crt")
        shutil.copy2(KEY_FILE, backup / "server.key")
        (backup / "server.key").chmod(0o600)
        try:
            os.replace(new_key, KEY_FILE)
            os.replace(new_cert, CERT_FILE)
            validate_pair()
        except BaseException:
            shutil.copy2(backup / "server.key", KEY_FILE)
            shutil.copy2(backup / "server.crt", CERT_FILE)
            KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
            raise
    return CERT_FILE, KEY_FILE, backup
