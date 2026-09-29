"""Actual NSS peer trust test in an isolated, disposable certificate database."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scratch_link_bleak_tls as tls
import scratch_link_bleak_setup as setup


@unittest.skipUnless(shutil.which("certutil"), "libnss3-tools is not available")
class NSSIntegrationTests(unittest.TestCase):
    def test_new_install_idempotence_and_certificate_rotation(self):
        with tempfile.TemporaryDirectory(prefix="scratch-nss-integration-") as directory:
            root = Path(directory)
            db = root / "nssdb"
            with (
                patch.object(tls, "CERT_DIR", root / "keys"),
                patch.object(tls, "CERT_FILE", root / "keys" / "server.crt"),
                patch.object(tls, "KEY_FILE", root / "keys" / "server.key"),
                patch.object(setup, "nss_database", return_value=db),
            ):
                tls.generate_certificate()
                old_fingerprint = tls.certificate_fingerprint()
                self.assertTrue(setup.install_browser_trust(ask=False))
                self.assertEqual(old_fingerprint, setup.installed_fingerprint(db))
                self.assertFalse(setup.install_browser_trust(ask=False))

                tls.renew_certificate(force=True)
                new_fingerprint = tls.certificate_fingerprint()
                self.assertNotEqual(old_fingerprint, new_fingerprint)
                self.assertTrue(setup.install_browser_trust(ask=False))
                self.assertEqual(new_fingerprint, setup.installed_fingerprint(db))
                self.assertFalse(setup.install_browser_trust(ask=False))


if __name__ == "__main__":
    unittest.main()
