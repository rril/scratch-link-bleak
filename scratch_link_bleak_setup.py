"""Opt-in desktop setup, Chrome NSS peer trust and systemd --user integration.

Only the public certificate is imported into NSS. We never disable TLS checks,
install a machine-wide CA, or silently modify /etc/hosts.
"""
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes

import scratch_link_bleak_tls as tls

NICKNAME = "Scratch Link Bleak Local Server"
SERVICE_NAME = "scratch-link-bleak.service"
SERVICE_HEADER = "# Managed by Scratch Link Bleak"


def confirm(message):
    if not sys.stdin.isatty():
        raise RuntimeError(message + " -- interactive terminal required; see README.")
    return input(f"{message} [y/N]: ").strip().casefold() in ("y", "yes")


def run(command, *, input_text=None, capture=False):
    return subprocess.run(
        command, input=input_text, text=True, check=True,
        capture_output=capture,
    )


def nss_database():
    legacy = Path.home() / ".pki" / "nssdb"
    modern = Path.home() / ".local" / "share" / "pki" / "nssdb"
    return legacy if legacy.is_dir() else modern


def installed_fingerprint(db):
    result = subprocess.run(
        ["certutil", "-d", f"sql:{db}", "-L", "-n", NICKNAME, "-a"],
        text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        return None
    try:
        begin = result.stdout.index("-----BEGIN CERTIFICATE-----")
        end = result.stdout.index("-----END CERTIFICATE-----", begin) + len("-----END CERTIFICATE-----")
        certificate = x509.load_pem_x509_certificate(
            result.stdout[begin:end].encode("ascii")
        )
        return certificate.fingerprint(hashes.SHA256()).hex().upper()
    except (ValueError, IndexError) as exc:
        raise RuntimeError("Existing NSS entry could not be decoded; inspect manually.") from exc


def install_browser_trust(*, ask=True):
    if shutil.which("certutil") is None:
        raise RuntimeError("certutil is missing; install libnss3-tools first.")
    tls.validate_pair()
    db = nss_database()
    db.mkdir(parents=True, exist_ok=True)
    if not (db / "cert9.db").exists():
        if ask and not confirm(f"Initialize local Chrome NSS database at {db}?"):
            return False
        # Never reinitialize or reset an existing certificate database.
        run(["certutil", "-d", f"sql:{db}", "-N", "--empty-password"])

    existing = installed_fingerprint(db)
    current = tls.certificate_fingerprint()
    if existing == current:
        print(f"Chrome NSS already trusts the current server certificate ({db}).")
        return False

    action = "Replace the existing Scratch Link Bleak peer certificate" if existing else "Trust the NEW Scratch Link Bleak certificate as a server peer"
    if ask and not confirm(f"{action} in {db}?"):
        print("Browser trust unchanged. You can repeat: scratch-link-bleak --install")
        return False

    previous_pem = None
    if existing:
        result = run(["certutil", "-d", f"sql:{db}", "-L", "-n", NICKNAME, "-a"], capture=True)
        previous_pem = result.stdout
        run(["certutil", "-d", f"sql:{db}", "-D", "-n", NICKNAME])
    try:
        run(["certutil", "-d", f"sql:{db}", "-A", "-t", "P,,",
             "-n", NICKNAME, "-i", str(tls.CERT_FILE)])
    except subprocess.CalledProcessError:
        if previous_pem:
            # Best-effort restoration of the previously trusted public certificate.
            result = subprocess.run(
                ["certutil", "-d", f"sql:{db}", "-A", "-t", "P,,", "-n", NICKNAME, "-a"],
                input=previous_pem, text=True, capture_output=True,
            )
            if result.returncode != 0:
                print("WARNING: old NSS peer trust could not be restored; see README.")
        raise
    if installed_fingerprint(db) != current:
        raise RuntimeError("Browser trust fingerprint mismatch after import")
    print(f"Imported verified public certificate into Chrome NSS ({db}).")
    print("Fully quit ALL Chrome processes and reopen Chrome for the change to take effect.")
    return True


def hosts_entries():
    result = []
    for line in Path("/etc/hosts").read_text().splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) >= 2 and tls.HOSTNAME in fields[1:]:
            result.append(fields[0])
    return result


def is_loopback():
    try:
        addresses = socket.gethostbyname_ex(tls.HOSTNAME)[2]
    except socket.gaierror:
        return False
    return bool(addresses) and all(a.startswith("127.") for a in addresses)


def configure_local_hostname(*, ask=True):
    entries = hosts_entries()
    if any(not a.startswith("127.") for a in entries):
        raise RuntimeError(
            "Conflicting /etc/hosts entry for Scratch hostname. Inspect with sudoedit /etc/hosts."
        )
    if is_loopback():
        print("Scratch device-manager hostname already resolves to local loopback.")
        return False
    if not ask or not confirm("Append 127.0.0.1 device-manager.scratch.mit.edu to /etc/hosts using sudo?"):
        print("Manually add to /etc/hosts using sudoedit: 127.0.0.1 " + tls.HOSTNAME)
        return False
    # Explicit permission is requested above; no shell interpolation of user input.
    run(["sudo", "tee", "-a", "/etc/hosts"],
        input_text="\n127.0.0.1 " + tls.HOSTNAME + "\n", capture=True)
    if not is_loopback():
        raise RuntimeError("Hostname still does not resolve to loopback; inspect /etc/hosts.")
    print("Local hostname mapping installed.")
    return True


def service_path():
    return Path.home() / ".config" / "systemd" / "user" / SERVICE_NAME


def service_active():
    if shutil.which("systemctl") is None:
        return False
    return subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    ).returncode == 0


def install_service(*, ask=True, start=True):
    if shutil.which("systemctl") is None:
        raise RuntimeError("systemctl not found: systemd --user is unavailable.")
    if not tls.CERT_FILE.is_file() or not tls.KEY_FILE.is_file():
        raise RuntimeError("First run scratch-link-bleak --install to generate TLS files.")
    path = service_path()
    if path.exists() and not path.read_text().startswith(SERVICE_HEADER):
        raise RuntimeError(f"Existing service at {path} is not managed by this application.")
    if ask and not confirm("Install and enable scratch-link-bleak as a systemd --user service?"):
        return False
    executable = sys.executable.replace("%", "%%").replace('"', r'\"')
    unit = (
        SERVICE_HEADER + "\n"
        "[Unit]\nDescription=Unofficial Scratch Link BLE bridge\n"
        "After=graphical-session.target\n\n"
        "[Service]\nType=simple\n"
        f'ExecStart="{executable}" -m scratch_link_bleak\n'
        "Restart=on-failure\nRestartSec=5\n\n"
        "[Install]\nWantedBy=default.target\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit)
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", "--now" if start else "--no-reload", SERVICE_NAME])
    print(f"Installed systemd user service: {path}")
    print("Use: systemctl --user status scratch-link-bleak")
    return True


def uninstall_service():
    path = service_path()
    if not path.is_file() or not path.read_text().startswith(SERVICE_HEADER):
        raise RuntimeError("No managed scratch-link-bleak.service found.")
    if not confirm(f"Disable and remove {path}?"):
        return False
    run(["systemctl", "--user", "disable", "--now", SERVICE_NAME])
    path.unlink()
    run(["systemctl", "--user", "daemon-reload"])
    print("Service removed. TLS keys, Chrome trust and /etc/hosts were preserved.")
    return True


def certificate_status(*, notify=False):
    if not tls.CERT_FILE.is_file() or not tls.KEY_FILE.is_file():
        print("No TLS files. Run scratch-link-bleak --install.")
        return 2
    tls.validate_pair()
    days = tls.days_remaining()
    expires = getattr(tls.read_certificate(), "not_valid_after_utc", None)
    if expires is None:
        expires = tls.read_certificate().not_valid_after.replace(tzinfo=timezone.utc)
    message = (
        f"Scratch Link Bleak TLS certificate expires on {expires.date()} "
        f"({days:.0f} days remaining)."
    )
    print(message)
    if days <= 30:
        warning = ("Certificate has expired!" if days <= 0 else
                   "Certificate expires within 30 days.")
        print("WARNING:", warning, "Run scratch-link-bleak --renew-certificate.")
        if notify and shutil.which("notify-send"):
            subprocess.run(["notify-send", "-u", "critical" if days <= 0 else "normal",
                            "Scratch Link Bleak certificate", message + "\nRun scratch-link-bleak --renew-certificate."],
                           check=False)
    return 2 if days <= 0 else (1 if days <= 30 else 0)


def renew_interactive(*, force=False):
    if service_active():
        raise RuntimeError(
            "Stop the running user service first: systemctl --user stop scratch-link-bleak"
        )
    if not tls.CERT_FILE.is_file() or not tls.KEY_FILE.is_file():
        raise RuntimeError("Missing TLS files. Run scratch-link-bleak --install.")
    days = tls.days_remaining()
    if days > 30 and not force:
        print(f"Certificate is not yet due for renewal ({days:.0f} days left).")
        return False
    print("Renewal changes the server fingerprint. Chrome MUST trust the new certificate.")
    print("The old key/certificate will be retained in a private backup directory.")
    if not confirm("Renew the local TLS server certificate now?"):
        return False
    cert, _key, backup = tls.renew_certificate(force=force)
    print(f"New certificate: {cert}; previous pair backed up to {backup}.")
    try:
        install_browser_trust(ask=True)
    except Exception as exc:
        print(f"New certificate generated, but NSS import failed: {exc}")
        print("Run scratch-link-bleak --install to import the new public certificate.")
        raise
    print("Restart Chrome completely, then restart the user service (if installed).")
    return True


def install_interactive():
    if os.geteuid() == 0:
        raise RuntimeError("Run as the desktop user, NOT with sudo.")
    if not tls.CERT_FILE.exists() and not tls.KEY_FILE.exists():
        if not confirm("Generate a new, private Scratch Link Bleak TLS certificate?"):
            return False
        tls.generate_certificate()
        print(f"Generated certificate at {tls.CERT_FILE} and private key at {tls.KEY_FILE}.")
    tls.validate_pair()
    if tls.days_remaining() <= 30:
        print("Certificate expires soon; renew it separately before installation.")
    install_browser_trust(ask=True)
    configure_local_hostname(ask=True)
    if confirm("Also install automatic startup via systemd --user?"):
        install_service(ask=False)
    print("Installation finished. Fully restart Chrome before testing Scratch.")
    if not is_loopback():
        print("ATTENTION: Scratch hostname must resolve to 127.0.0.1; see instructions above.")
    return True
