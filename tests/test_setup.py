"""Hardware-free tests for certificate lifecycle and safe desktop setup."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography import x509

import scratch_link_bleak_tls as tls
import scratch_link_bleak_setup as setup


class CertificateLifecycleTests(unittest.TestCase):
    def test_generate_renew_backup_and_no_silent_early_renewal(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            with (
                patch.object(tls, "CERT_DIR", directory),
                patch.object(tls, "CERT_FILE", directory / "server.crt"),
                patch.object(tls, "KEY_FILE", directory / "server.key"),
            ):
                cert, key = tls.generate_certificate()
                original = tls.certificate_fingerprint()
                self.assertGreater(tls.days_remaining(), 300)
                with self.assertRaises(ValueError):
                    tls.renew_certificate()
                self.assertEqual(original, tls.certificate_fingerprint())
                cert, key, backup = tls.renew_certificate(force=True)
                self.assertNotEqual(original, tls.certificate_fingerprint())
                self.assertEqual(original, tls.certificate_fingerprint(backup / "server.crt"))
                self.assertEqual((backup / "server.key").stat().st_mode & 0o777, 0o600)
                self.assertTrue(cert.is_file() and key.is_file())
                self.assertFalse(
                    tls.read_certificate().extensions.get_extension_for_class(
                        x509.BasicConstraints
                    ).value.ca
                )


class SetupTests(unittest.TestCase):
    def test_browser_trust_uses_public_cert_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            cert = directory / "server.crt"
            key = directory / "server.key"
            with (
                patch.object(tls, "CERT_DIR", directory),
                patch.object(tls, "CERT_FILE", cert),
                patch.object(tls, "KEY_FILE", key),
                patch.object(setup, "nss_database", return_value=directory / "nssdb"),
                patch.object(setup, "confirm", return_value=True),
                patch.object(setup.shutil, "which", return_value="/usr/bin/certutil"),
            ):
                tls.generate_certificate()
                db = directory / "nssdb"
                db.mkdir()
                (db / "cert9.db").touch()
                current = tls.certificate_fingerprint()
                calls = []
                def fake_run(command, **kwargs):
                    calls.append(command)
                    return SimpleNamespace(stdout="")
                with (patch.object(setup, "run", side_effect=fake_run),
                      patch.object(setup, "installed_fingerprint", side_effect=[None, current, current])):
                    self.assertTrue(setup.install_browser_trust())
                    self.assertFalse(setup.install_browser_trust())
                additions = [cmd for cmd in calls if "-A" in cmd]
                self.assertEqual(len(additions), 1)
                self.assertEqual(additions[0][additions[0].index("-t") + 1], "P,,")
                self.assertEqual(additions[0][-1], str(cert))
                self.assertNotIn(str(key), " ".join(additions[0]))

    def test_hostname_changes_require_consent(self):
        with (
            patch.object(setup, "hosts_entries", return_value=[]),
            patch.object(setup, "is_loopback", side_effect=[False]),
            patch.object(setup, "confirm", return_value=False),
            patch.object(setup, "run") as run,
        ):
            self.assertFalse(setup.configure_local_hostname())
            run.assert_not_called()

    def test_conflicting_hostname_is_not_overwritten(self):
        with patch.object(setup, "hosts_entries", return_value=["192.0.2.1"]):
            with self.assertRaises(RuntimeError):
                setup.configure_local_hostname()

    def test_service_and_timer_created_without_sudo(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            cert = directory / "server.crt"
            key = directory / "server.key"
            path = directory / "systemd" / "scratch-link-bleak.service"
            with (
                patch.object(tls, "CERT_DIR", directory),
                patch.object(tls, "CERT_FILE", cert),
                patch.object(tls, "KEY_FILE", key),
                patch.object(setup, "service_path", return_value=path),
                patch.object(setup.shutil, "which", return_value="/usr/bin/systemctl"),
                patch.object(setup, "run") as run,
            ):
                tls.generate_certificate()
                self.assertTrue(setup.install_service(ask=False))
                self.assertIn("-m scratch_link_bleak", path.read_text())
                self.assertIn("WantedBy=default.target", path.read_text())
                self.assertIn("OnCalendar=weekly", (path.parent / "scratch-link-bleak-cert-check.timer").read_text())
                self.assertNotIn("sudo", path.read_text())
                commands = [call.args[0] for call in run.call_args_list]
                self.assertIn(["systemctl", "--user", "enable", "--now", "scratch-link-bleak.service"], commands)
                self.assertIn(["systemctl", "--user", "enable", "--now", "scratch-link-bleak-cert-check.timer"], commands)

if __name__ == "__main__":
    unittest.main()
