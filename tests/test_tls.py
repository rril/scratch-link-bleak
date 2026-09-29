"""Certificate generation tests (no Bluetooth hardware required)."""
import os
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

import scratch_link_bleak_tls as tls


class CertificateTests(unittest.TestCase):
    def test_generate_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            with (
                patch.object(tls, "CERT_DIR", dest),
                patch.object(tls, "CERT_FILE", dest / "server.crt"),
                patch.object(tls, "KEY_FILE", dest / "server.key")
            ):
                cert_path, key_path = tls.generate_certificate()
                self.assertTrue(cert_path.is_file())
                self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)

                cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
                san = cert.extensions.get_extension_for_class(
                    x509.SubjectAlternativeName
                ).value
                self.assertIn(tls.HOSTNAME, san.get_values_for_type(x509.DNSName))
                basic = cert.extensions.get_extension_for_class(
                    x509.BasicConstraints
                ).value
                self.assertFalse(basic.ca)
                eku = cert.extensions.get_extension_for_class(
                    x509.ExtendedKeyUsage
                ).value
                self.assertIn(ExtendedKeyUsageOID.SERVER_AUTH, eku)

                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(str(cert_path), str(key_path))
                before = key_path.read_bytes()
                with self.assertRaises(FileExistsError):
                    tls.generate_certificate()
                self.assertEqual(before, key_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
