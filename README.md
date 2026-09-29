# Scratch Link Bleak

**Unofficial, experimental Scratch Link BLE bridge for Linux** using [Bleak](https://github.com/hbldh/bleak) (BlueZ/D-Bus) rather than bluepy. No installation of pyscrlink or reuse of its files is needed.

**Verified setup (previous prototype):** LEGO WeDo 2.0 (LPF2 Smart Hub), Ubuntu 24.04.5 LTS, Chrome and the official [Scratch editor](https://scratch.mit.edu/projects/editor/). A one-hour hardware session was successful and the disconnect flood was corrected. **The new standalone certificate setup needs fresh on-device verification.**

## Why?

On one Ubuntu machine, the WeDo 2.0 repeatedly disconnected via pyscrlink 0.2.8 with `BTLEException: Error from bluepy-helper (badstate)` during a GATT write. Equivalent GATT operations via Bleak succeeded, so this experimental bridge retains the Scratch Link WebSocket protocol while replacing the Bluetooth implementation.

## Requirements

- Linux desktop with BlueZ and a working BLE adapter, Python >= 3.10.
- Chrome (or compatible Chromium) and the official Scratch editor.
- OpenSSL is optional for inspecting the public certificate.
- `libnss3-tools` to import the public certificate into Chrome's NSS store.
- No `pyscrlink`, `bluepy`, or `bluepy-helper` installation required.

## Standalone installation (development branch)

```bash
sudo apt install python3-venv libnss3-tools
git clone https://github.com/rril/scratch-link-bleak.git
cd scratch-link-bleak
git switch initial-bleak-release   # omit after PR #1 is merged
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
- [x] Independent TLS certificate generator and documented manual Chrome trust setup (**needs device testing**).
- [ ] WebSocket/reconnect regression suite and better installer UX.
- [ ] Additional hardware support, optional systemd user service.
- [ ] License/provenance review before a tagged public release or PyPI upload.

## Acknowledgements

Thanks to [pyscrlink](https://github.com/kawasaki/pyscrlink) for its Linux Scratch Link contribution and compatibility context. This independent community project is **not affiliated with or endorsed by Scratch, LEGO, or pyscrlink**.

Please report reproducible logs in Issues. Never post private keys.
