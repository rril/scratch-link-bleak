# Scratch Link Bleak

[![Python smoke tests](https://github.com/rril/scratch-link-bleak/actions/workflows/python.yml/badge.svg)](https://github.com/rril/scratch-link-bleak/actions/workflows/python.yml)

**Unofficial, experimental Scratch Link BLE bridge for Linux** using [Bleak](https://github.com/hbldh/bleak) (BlueZ/D-Bus) rather than bluepy. No installation of pyscrlink or reuse of its files is needed.

**Verified setup:** LEGO WeDo 2.0 (LPF2 Smart Hub), Ubuntu 24.04.5 LTS, Chrome and the official [Scratch editor](https://scratch.mit.edu/projects/editor/). A one-hour hardware session was successful. The standalone installation was separately verified in a fresh Python environment without pyscrlink/bluepy: new TLS certificate and Chrome trust, motor and sensors, disconnect and reconnect. Other hardware and distributions remain untested.

## Why?

On one Ubuntu machine, the WeDo 2.0 repeatedly disconnected via pyscrlink 0.2.8 with `BTLEException: Error from bluepy-helper (badstate)` during a GATT write. Equivalent GATT operations via Bleak succeeded, so this experimental bridge retains the Scratch Link WebSocket protocol while replacing the Bluetooth implementation.

## v0.3 installer preview

v0.3 introduces an **interactive guided installer** that does not require manually
copying certificate commands. The v0.2.0b1 release remains available while this
development branch undergoes testing.

To test v0.3 **from this feature branch**, install into a fresh virtual environment:

```bash
sudo apt install python3-venv libnss3-tools
git clone https://github.com/rril/scratch-link-bleak.git
cd scratch-link-bleak
git switch feature/installer-cert-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
scratch-link-bleak --install
```

The installer asks **separately** before each change:
1. Generate a private TLS key and local self-signed server (non-CA) certificate,
   or reuse the existing valid pair.
2. Import **only the public certificate** into the standard Chrome/Chromium NSS
   database as a trusted peer (`P,,`). It never installs a system-wide CA.
3. Add `127.0.0.1 device-manager.scratch.mit.edu` to `/etc/hosts` using
   `sudo tee -a` **only with your explicit permission**, and only when no
   conflicting hosts entry exists. You can instead use `sudoedit /etc/hosts`.
4. Optionally install and enable a `systemd --user` service for automatic
   startup on login, plus a weekly certificate-expiry reminder timer.

**Restart Chrome completely** after initial setup or certificate renewal.
The installer targets standard Chrome/Chromium NSS paths on Linux, not custom
Snap/Flatpak browser trust stores. Run it as your regular desktop user, not root.

Available maintenance commands:

| Command | Purpose |
|---|---|
| `scratch-link-bleak --install` | Interactive, safe-to-rerun desktop setup |
| `scratch-link-bleak --certificate-status` | Show expiry date and warning |
| `scratch-link-bleak --renew-certificate` | Renew when 30 days or fewer remain, with confirmation and Chrome trust update |
| `scratch-link-bleak --renew-certificate --force-renew` | Explicitly rotate a still-valid certificate |
| `scratch-link-bleak --install-service` | Opt in to service and weekly reminder timer |
| `scratch-link-bleak --remove-service` | Disable/remove our managed service and reminder only |
| `scratch-link-bleak --setup` | Legacy option: generate TLS files without importing browser trust |

### Certificate lifecycle / renewal

The server warns at startup when the certificate has at most 30 days remaining
and refuses to start with an expired certificate. If you chose the systemd user
service, the weekly `scratch-link-bleak-cert-check.timer` also runs a desktop
notification (when `notify-send` is available).

**Do not silently rotate a trusted server peer:** Chrome trusts the specific
certificate fingerprint, and renewing it creates a new fingerprint. The
`--renew-certificate` command therefore requires confirmation, preserves the
old certificate/key in a private `backups/` directory, and offers to replace
the matching NSS peer trust. Stop the bridge first:

```bash
systemctl --user stop scratch-link-bleak  # if you installed the user service
scratch-link-bleak --renew-certificate
# Completely quit Chrome and reopen it before using Scratch.
systemctl --user start scratch-link-bleak # if the service was installed
```

For a manually started server, stop that process before renewal. If the NSS
import is interrupted, run `scratch-link-bleak --install` again to trust the
new public certificate. The old TLS pair remains in
`~/.local/share/scratch-link-bleak/backups/` for manual recovery. Never share
the private key or include backups in Git.

### User service

```bash
scratch-link-bleak --install-service
systemctl --user status scratch-link-bleak
systemctl --user status scratch-link-bleak-cert-check.timer
journalctl --user -u scratch-link-bleak -f
```

Routine Scratch requests and individual BLE writes are logged only with `--debug`, not at the default INFO level. The systemd service uses INFO to avoid flooding the journal. Important connection/disconnection events and errors remain visible. For a temporary detailed trace, stop the service and run `scratch-link-bleak --debug` manually, then restart the service when finished.

This is a **per-user process**; it does not require running the BLE server as
root. The service stores the exact Python interpreter path from installation,
so reinstall it if you move/recreate the virtual environment or pipx installation.
To undo autostart without touching TLS keys, Chrome trust or /etc/hosts:

```bash
scratch-link-bleak --remove-service
```

---

## Requirements

- Linux desktop with BlueZ and a working BLE adapter, Python >= 3.10.
- Chrome (or compatible Chromium) and the official Scratch editor.
- OpenSSL is optional for inspecting the public certificate.
- `libnss3-tools` to import the public certificate into Chrome's NSS store.
- No `pyscrlink`, `bluepy`, or `bluepy-helper` installation required.

## Standalone installation

```bash
sudo apt install python3-venv libnss3-tools
git clone https://github.com/rril/scratch-link-bleak.git
cd scratch-link-bleak
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
scratch-link-bleak --setup
```

`--setup` generates:

- `~/.local/share/scratch-link-bleak/server.crt`: public, self-signed TLS server certificate with SAN `device-manager.scratch.mit.edu`.
- `~/.local/share/scratch-link-bleak/server.key`: private key (mode 0600). **Never publish this file.**

The tool refuses to replace existing certificate/key files. It **does not automatically alter browser trust, your hosts file, or the system certificate store**.

### Configure local hostname

Check the current mapping:

```bash
getent ahostsv4 device-manager.scratch.mit.edu
```

For local Scratch Link operation, ensure `device-manager.scratch.mit.edu` resolves to `127.0.0.1`. If it does not, use `sudoedit /etc/hosts` to add this line (preserve existing entries):

```text
127.0.0.1 device-manager.scratch.mit.edu
```

Only do this on the machine running the bridge, not on a remote server.

### Trust the NEW public certificate in Chrome (Linux NSS)

Chromium's [Linux certificate management documentation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/docs/linux/cert_management.md) specifies `P,,` for a trusted self-signed TLS server **peer**. Import only the generated **public** `server.crt`; do not import the private key.

Newer Chromium (M146+) defaults to `~/.local/share/pki/nssdb`, but continues to use `~/.pki/nssdb` if the latter already exists. Choose **one** directory according to the Chrome profile in use:

```bash
if [ -d "$HOME/.pki/nssdb" ]; then
    NSSDB="$HOME/.pki/nssdb"
else
    NSSDB="$HOME/.local/share/pki/nssdb"
fi
mkdir -p "$NSSDB"
# Only initialize a *missing* database, never reset an existing one:
if [ ! -f "$NSSDB/cert9.db" ]; then
    certutil -d "sql:$NSSDB" -N --empty-password
fi
certutil -d "sql:$NSSDB" -A -t "P,," \
  -n "Scratch Link Bleak Local Server" \
  -i "$HOME/.local/share/scratch-link-bleak/server.crt"
certutil -d "sql:$NSSDB" -L -n "Scratch Link Bleak Local Server"
```

If your NSS database is password protected, use `certutil -N` without `--empty-password` for initialization and unlock it as prompted. A Chrome installed through Flatpak/Snap may use a different certificate store; the examples here target standard Chrome on Ubuntu.

**Fully close Chrome and reopen it** after importing the certificate.

### Start

Ensure the original Scratch Link (if installed) is not running on TCP port 20110:

```bash
ss -ltnp | grep ':20110' || true
scratch-link-bleak
```

The process binds **only** to `127.0.0.1:20110`, serves `wss://device-manager.scratch.mit.edu:20110/scratch/ble`, and uses the generated TLS certificate.

Open [Scratch editor](https://scratch.mit.edu/projects/editor/) in Chrome, enable LEGO WeDo 2.0, and connect to **LPF2 Smart Hub**. Test motor, sensor, power off, and reconnect. Run as a regular desktop user, not root.

Optional flags: `--debug`, `--scan-seconds 15`.

### Proving independence from pyscrlink

- `python -m pip show scratch-link-bleak bleak websockets cryptography` should show installed dependencies.
- `python -m pip show pyscrlink bluepy` should say the packages are absent in the new virtual environment.
- The bridge reads **only** `~/.local/share/scratch-link-bleak/{server.crt,server.key}`.
- If you have an old `~/.local/share/pyscrlink`, **rename it temporarily**, rather than deleting it, while testing this installation. A previously installed Chrome trust entry for the old certificate may remain, but will **not** validate the newly generated, distinct server certificate.

### Troubleshooting

- Certificate error in Chrome: check correct NSS database, peer trust `P,,`, fully restart Chrome, verify the public certificate has the expected SAN; never bypass certificate checks globally.
- Connection refused: check port 20110, that the bridge is running, and the hostname mapping.
- No WeDo discovered: close other BLE connections, power-cycle the hub and retry.

## Limitations and roadmap

- [x] Discovery, connect, read, write and notifications over Bleak for LEGO WeDo 2.0.
- [x] Suppress traceback flood for queued operations after BLE disconnect.
- [x] Independent TLS certificate generator and documented manual Chrome trust setup (verified on Ubuntu 24.04.5 LTS + Chrome).
- [x] Guided installer (v0.3 preview; hardware acceptance testing pending).\n- [x] Certificate expiry warning and explicit renewal (v0.3 preview; hardware acceptance testing pending).\n- [ ] WebSocket/reconnect regression suite.
- [x] Optional systemd user service and weekly expiry check (v0.3 preview; testing pending).\n- [ ] Additional hardware support.
- [x] BSD 3-Clause license, retaining the original pyscrlink copyright notice.
- [ ] Test on additional Linux distributions and hardware before claiming broader support.

## License and adoption

[BSD 3-Clause](LICENSE). Commercial use, modification, proprietary redistribution and integration into an official product are permitted under the license conditions, including retaining the applicable notices and not implying endorsement.

LEGO, the Scratch Foundation, and others are welcome to adopt or contribute to this project. This invitation does not imply affiliation or endorsement, or grant any trademark rights.

## Acknowledgements

Thanks to [pyscrlink](https://github.com/kawasaki/pyscrlink) for its Linux Scratch Link contribution and compatibility context. This independent community project is **not affiliated with or endorsed by Scratch, LEGO, or pyscrlink**.

Please report reproducible logs in Issues. Never post private keys.
