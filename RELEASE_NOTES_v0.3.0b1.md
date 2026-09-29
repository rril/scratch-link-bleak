## Scratch Link Bleak v0.3.0 Beta 1

Unofficial Scratch Link-compatible BLE bridge for Linux, using Bleak (BlueZ/D-Bus).

### New in this beta
- **Guided setup:** `scratch-link-bleak --install` generates or reuses a local TLS certificate, helps trust its public certificate in Chrome NSS, requests consent for the local hostname entry and optionally installs a user-level service.
- **Certificate lifecycle:** `--certificate-status` reports expiry, startup warns within 30 days, and `--renew-certificate` rotates the server certificate with confirmation and recoverable private backups. Chrome trust update is explicit; renewal is never silent.
- **Automatic startup:** Optional `systemd --user` service, restart-on-failure and weekly certificate-expiry reminder.
- **Quieter logs:** routine Scratch RPC requests and successful BLE writes are DEBUG-only, avoiding INFO-level journal spam.
- Tests include certificate import and renewal in an isolated NSS database.

### Verified hardware
Ubuntu 24.04.5 LTS / Google Chrome / LEGO WeDo 2.0. Guided installation, user service, motor and sensor operation, and multiple physical disconnection/reconnection cycles verified. Other hardware and Linux distributions are not yet confirmed.

### Install

```bash
sudo apt install pipx libnss3-tools
pipx ensurepath
pipx install 'scratch-link-bleak==0.3.0b1'
scratch-link-bleak --install
```

If installed using pipx already, use `pipx upgrade scratch-link-bleak --pip-args='--pre'`. Fully restart Chrome after changing certificate trust.

See the [README](https://github.com/rril/scratch-link-bleak#readme) for details.

**BSD 3-Clause.** Commercial use and official adoption welcome. Unofficial; not affiliated with Scratch or LEGO.
