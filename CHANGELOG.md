# Changelog

## 0.3.0b1 — guided desktop setup (unreleased candidate)

- Interactive `scratch-link-bleak --install` for private server certificate generation, public Chrome NSS peer trust, optional local hosts entry (explicit sudo consent), and optional per-user autostart.
- `--certificate-status` and startup warning within 30 days of TLS expiry; no startup using an expired certificate.
- Explicit `--renew-certificate` with recoverable private backups and Chrome trust update. Silent certificate replacement is deliberately avoided.
- Optional `systemd --user` service, accompanied by a weekly expiry reminder timer and `--remove-service`.
- Unit tests for expiry, rotation, Chrome peer trust, consent, and service unit generation.
- Routine JSON-RPC requests and BLE writes moved from INFO to DEBUG to avoid flooding systemd journal.
- Owner-verified Ubuntu/Chrome/WeDo acceptance test: installation and user service, motor and sensors, power-off/disconnect and multiple reconnects succeeded.
- Current beta release v0.2.0b1 remains available until v0.3.0b1 is published.

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
