# Scratch Link Bleak

**Unofficial, experimental Scratch Link BLE bridge for Linux** using [Bleak](https://github.com/hbldh/bleak) (BlueZ/D-Bus) instead of bluepy.

**Verified setup:** LEGO WeDo 2.0 (LPF2 Smart Hub), Ubuntu 24.04.5 LTS, Chrome and the official [Scratch editor](https://scratch.mit.edu/projects/editor/). A real-world session ran continuously for an hour, including motor/sensor use. v0.1.1 additionally addresses noisy errors when the hub is switched off. Other hardware and distributions have **not** been tested.

> **Prototype caveat:** This version reuses an existing, locally trusted TLS certificate from [pyscrlink](https://github.com/kawasaki/pyscrlink). It isn't a fully independent drop-in installation yet. Never publish your private key.

## Why?

On one Ubuntu system, the WeDo 2.0 would connect via pyscrlink 0.2.8 and then fail during a write with `BTLEException: Error from bluepy-helper (badstate)`. An equivalent test built with Bleak completed discovery, connection, writes, notifications, the previously failing write, and a 30-second hold. This alternative retains Scratch's local BLE WebSocket interface while changing the Bluetooth implementation.

## Install and run (current development branch)

Requires Linux with BlueZ, a BLE adapter, Python 3.10+, Chrome, and an existing pyscrlink TLS setup.

The certificate and key must exist locally at:

- `~/.local/share/pyscrlink/scratch-device-manager.cer`
- `~/.local/share/pyscrlink/scratch-device-manager.key` (**private; never commit**)

Ensure `device-manager.scratch.mit.edu` resolves to `127.0.0.1` locally and Chrome trusts the already configured certificate. Stop the original `scratch_link` process first, since both bridges use port 20110.

```bash
git clone https://github.com/rril/scratch-link-bleak.git
cd scratch-link-bleak
git switch initial-bleak-release  # only until the pull request is merged
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
scratch-link-bleak
```

Optional flags: `--debug` for detailed logs; `--scan-seconds 15` to adjust scanning duration.

In Chrome, open [Scratch](https://scratch.mit.edu/projects/editor/), add the LEGO WeDo 2.0 extension, and connect to LPF2 Smart Hub. Run the bridge as your regular desktop user, **not with sudo**.

## Security and limitations

- TLS server binds to `127.0.0.1:20110` and accepts only `/scratch/ble`. It refuses startup if its hostname does not resolve to loopback.
- This prototype allows only two known WeDo 2.0 GATT services. No other Scratch hardware extension is currently verified.
- Certificate/key setup is not yet automated. Do not commit, share, or upload any generated private key.
- This is a public **review candidate**, not yet released on PyPI.

## Roadmap

- [x] WeDo discovery, connect, read, write, notifications over Bleak
- [x] Quiet handling of queued BLE operations after disconnect
- [ ] Independent TLS setup / certificate trust instructions
- [ ] WebSocket protocol and reconnect regression tests
- [ ] Additional hardware testing, packaging, optional systemd user service
- [ ] License and provenance review before public release tag

## Acknowledgements

Thanks to [pyscrlink](https://github.com/kawasaki/pyscrlink), whose Linux Scratch Link work provided compatibility context. Scratch and LEGO are trademarks of their respective owners. This community project is **not affiliated with or endorsed by Scratch, LEGO, or pyscrlink**.

Issues and reproducible logs are welcome. Please never include private keys; redact addresses and personal paths as appropriate.
