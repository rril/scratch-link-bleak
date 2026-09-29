# Changelog

## 0.2.0b1 — standalone TLS beta (2026-09-29)

- Generate an independent self-signed server certificate with `scratch-link-bleak --setup`.
- Store certificate and private key under `~/.local/share/scratch-link-bleak/`, no dependency on pyscrlink files.
- Add separate Chrome/NSS trust instructions (trusted peer certificate) and localhost hostname setup.
- Add certificate generator unit test (SAN, EKU, key permissions, no overwrite, SSL loading).
- Successfully tested end-to-end without pyscrlink or bluepy, with a new TLS certificate trusted in Chrome, and with motors, sensors and reconnection working.
- Adopt BSD-3-Clause license, retaining upstream pyscrlink copyright notice.

## 0.1.1 — initial review candidate (2026-09-29)

- Initial WeDo 2.0 / Scratch / Ubuntu bridge tested on local hardware.
- Bleak replaces bluepy for discovery, connection, GATT writes and notifications.
- Treat queued requests following hub disconnect as expected errors, avoiding traceback floods.
- Add installable console entry point and basic discovery tests.

No PyPI release or GitHub release tag has been created yet.
