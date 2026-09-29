#!/usr/bin/env python3
"""Experimental Scratch Link replacement for LEGO WeDo 2.0 (Linux, Bleak).
Run as your desktop user, not root. Requires bleak and websockets==13.1.
"""
import argparse
import asyncio
import base64
import json
import logging
import socket
import ssl
from pathlib import Path

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from websockets.legacy.server import serve
from websockets.exceptions import ConnectionClosed

HOSTNAME = 'device-manager.scratch.mit.edu'
PORT = 20110
WEDO_SERVICE = '00001523-1212-efde-1523-785feabcd123'
WEDO_IO_SERVICE = '00004f0e-1212-efde-1523-785feabcd123'
LOG = logging.getLogger('scratch-link-bleak')
# This experimental implementation only supports the known WeDo services.
ALLOWED = {WEDO_SERVICE, WEDO_IO_SERVICE}


def matches(device, adv, filters):
    services = {str(x).lower() for x in adv.service_uuids}
    name = adv.local_name or device.name or ''
    for f in filters:
        if f.get('name') is not None and f['name'] != name:
            continue
        if f.get('namePrefix') is not None and not name.startswith(f['namePrefix']):
            continue
        if not {str(x).lower() for x in f.get('services', [])}.issubset(services):
            continue
        if 'manufacturerData' in f:
            good = True
            for company, rule in f['manufacturerData'].items():
                data = adv.manufacturer_data.get(int(company))
                if data is None:
                    good = False
                    break
                prefix = rule.get('dataPrefix', []) if isinstance(rule, dict) else []
                mask = rule.get('mask', [255] * len(prefix)) if isinstance(rule, dict) else []
                if len(data) < len(prefix) or len(mask) != len(prefix) or any(
                    (data[i] & mask[i]) != (v & mask[i]) for i, v in enumerate(prefix)
                ):
                    good = False
                    break
            if not good:
                continue
        return True
    return False


class Session:
    def __init__(self, ws, scan_seconds):
        self.ws = ws
        self.scan_seconds = scan_seconds
        self.state = 'initial'
        self.devices = []
        self.client = None
        self.allowed_services = set()
        self.notifying = set()
        self.send_lock = asyncio.Lock()
        self.tasks = set()
        self.stale_requests = 0
        self.closing = False

    async def send(self, obj):
        async with self.send_lock:
            await self.ws.send(json.dumps(obj))

    async def event(self, method, params):
        await self.send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def schedule(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        def log_error(t):
            if not t.cancelled() and t.exception() is not None:
                LOG.warning('Notification send: %s', t.exception())
        task.add_done_callback(log_error)

    def disconnected(self, client):
        if not self.closing and self.state != 'disconnected':
            LOG.warning('WeDo Bluetooth link disconnected')
        self.state = 'disconnected'

    def characteristic(self, params):
        if self.client is None or not self.client.is_connected:
            raise RuntimeError('Not connected to WeDo')
        service_id = str(params.get('serviceId', '')).lower()
        char_id = str(params['characteristicId']).lower()
        if service_id not in self.allowed_services or service_id not in ALLOWED:
            raise ValueError('Service is not allowed: ' + service_id)
        service = self.client.services.get_service(service_id)
        if service is None:
            raise ValueError('Service not found: ' + service_id)
        characteristic = service.get_characteristic(char_id)
        if characteristic is None:
            raise ValueError('Characteristic not found in service: ' + char_id)
        return characteristic, service_id, char_id

    async def start_notifications(self, params):
        char, service_id, char_id = self.characteristic(params)
        if char_id in self.notifying:
            return
        def callback(_sender, data):
            if self.closing or self.state != 'connected':
                return
            self.schedule(self.event('characteristicDidChange', {
                'serviceId': service_id,
                'characteristicId': char_id,
                'encoding': 'base64',
                'message': base64.b64encode(data).decode('ascii'),
            }))
        await self.client.start_notify(char, callback)
        self.notifying.add(char_id)
        LOG.info('Notifications enabled: %s', char_id)

    async def request(self, method, params):
        if method == 'getVersion':
            return {'protocol': '1.3', 'implementation': 'scratch-link-bleak experimental'}

        if method == 'discover' and self.state == 'initial':
            filters = params.get('filters', [])
            if not filters or not any(f.get('services') or f.get('name') or f.get('namePrefix') for f in filters):
                raise ValueError('Nonempty discovery filters required')
            # Only WeDo 2.0 is supported by this experimental bridge.
            if not any(WEDO_SERVICE in [str(x).lower() for x in f.get('services', [])] for f in filters):
                raise ValueError('Only LEGO WeDo 2.0 is supported')
            self.allowed_services = {str(x).lower() for f in filters for x in f.get('services', [])}
            self.allowed_services.update(str(x).lower() for x in params.get('optionalServices', []))
            LOG.info('Scanning for WeDo (%.1fs)', self.scan_seconds)
            found = await BleakScanner.discover(timeout=self.scan_seconds, return_adv=True)
            self.devices = [(dev, adv) for dev, adv in found.values() if matches(dev, adv, filters)]
            self.state = 'discovery'
            LOG.info('Discovered %s matching device(s)', len(self.devices))
            return None

        if method == 'connect' and self.state == 'discovery':
            idx = int(params['peripheralId'])
            if idx < 0 or idx >= len(self.devices):
                raise ValueError('Unknown peripheralId')
            dev, _ = self.devices[idx]
            LOG.info('Connecting to %s', dev.name)
            self.client = BleakClient(dev, disconnected_callback=self.disconnected, timeout=20)
            await self.client.connect()
            self.state = 'connected'
            LOG.info('Connected; GATT services ready')
            return None

        if self.state != 'connected':
            raise ValueError('Method not available in state ' + self.state)

        if method == 'getServices':
            return [s.uuid for s in self.client.services if s.uuid.lower() in self.allowed_services and s.uuid.lower() in ALLOWED]
        if method == 'getCharacteristics':
            sid = str(params['serviceId']).lower()
            if sid not in self.allowed_services or sid not in ALLOWED:
                raise ValueError('Service not allowed')
            svc = self.client.services.get_service(sid)
            return [c.uuid for c in svc.characteristics] if svc else []
        if method == 'write':
            char, _, _ = self.characteristic(params)
            encoding = params.get('encoding', 'utf8')
            if encoding == 'base64':
                payload = base64.b64decode(params['message'], validate=True)
            elif encoding in ('utf8', 'utf-8'):
                payload = params['message'].encode('utf-8')
            else:
                raise ValueError('Unsupported encoding: ' + str(encoding))
            if 'withResponse' in params:
                response = bool(params['withResponse'])
            else:
                response = 'write-without-response' not in char.properties
            await self.client.write_gatt_char(char, payload, response=response)
            LOG.info('Write %s: %s bytes (response=%s)', char.uuid, len(payload), response)
            return len(payload)
        if method == 'read':
            char, _, _ = self.characteristic(params)
            data = await self.client.read_gatt_char(char)
            result = {'message': base64.b64encode(data).decode('ascii'), 'encoding': 'base64'}
            if params.get('startNotifications'):
                await self.start_notifications(params)
            return result
        if method == 'startNotifications':
            await self.start_notifications(params)
            return None
        if method == 'stopNotifications':
            char, _, char_id = self.characteristic(params)
            if char_id in self.notifying:
                await self.client.stop_notify(char)
                self.notifying.remove(char_id)
            return None
        raise ValueError('Unsupported method: ' + method)

    async def run(self):
        try:
            async for raw in self.ws:
                req = None
                try:
                    req = json.loads(raw)
                    if req.get('jsonrpc') != '2.0':
                        raise ValueError('Expected JSON-RPC 2.0')
                    method = req['method']
                    params = req.get('params') or {}
                    LOG.info('Request: %s', method)
                    result = await self.request(method, params)
                    if 'id' in req:
                        # Keep pyscrlink's legacy no-result response for start/stopNotifications.
                        if method in ('startNotifications', 'stopNotifications'):
                            await self.send({'jsonrpc': '2.0', 'id': req['id']})
                        else:
                            await self.send({'jsonrpc': '2.0', 'id': req['id'], 'result': result})
                    if method == 'discover':
                        for idx, (dev, adv) in enumerate(self.devices):
                            await self.event('didDiscoverPeripheral', {
                                'rssi': adv.rssi if adv.rssi is not None else 127,
                                'peripheralId': idx,
                                'name': adv.local_name or dev.name or 'LPF2 Smart Hub',
                            })
                except Exception as exc:
                    # Scratch may have a burst of writes already queued when the
                    # hub disconnects. They are expected failures, not crashes.
                    stale = self.state == 'disconnected' and (
                        isinstance(exc, (ValueError, RuntimeError, BleakError))
                    )
                    if stale:
                        self.stale_requests += 1
                        if self.stale_requests == 1:
                            LOG.info('Ignoring BLE operations queued after hub disconnect')
                    else:
                        LOG.exception('Request failed: %s', exc)
                    if isinstance(req, dict) and 'id' in req:
                        await self.send({'jsonrpc': '2.0', 'id': req['id'],
                                         'error': {'code': -32000, 'message': str(exc)}})
        except ConnectionClosed:
            LOG.info('WebSocket closed')
        finally:
            self.closing = True
            if self.stale_requests:
                LOG.info('Rejected %d queued request(s) after BLE disconnect', self.stale_requests)
            for task in self.tasks:
                task.cancel()
            if self.client and self.client.is_connected:
                try:
                    await self.client.disconnect()
                except Exception:
                    LOG.exception('Error disconnecting BLE')
            LOG.info('Session finished')


async def main():
    parser = argparse.ArgumentParser(description='Experimental WeDo 2.0 Scratch Link using Bleak')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-s', '--scan-seconds', type=float, default=10)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    cert_dir = Path.home() / '.local/share/pyscrlink'
    cert = cert_dir / 'scratch-device-manager.cer'
    key = cert_dir / 'scratch-device-manager.key'
    if not cert.is_file() or not key.is_file():
        raise SystemExit(f'Existing pyscrlink TLS certificate not found in {cert_dir}. Run original scratch_link once first.')
    resolved = socket.gethostbyname(HOSTNAME)
    if not resolved.startswith('127.'):
        raise SystemExit(f'{HOSTNAME} resolves to {resolved}, not loopback. Check local /etc/hosts mapping.')
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert), str(key))
    async def handler(ws, path):
        LOG.info('WebSocket path %s', path)
        if path != '/scratch/ble':
            await ws.close(code=1008, reason='Only /scratch/ble is supported')
            return
        await Session(ws, args.scan_seconds).run()
    async with serve(handler, '127.0.0.1', PORT, ssl=ctx, max_size=2**20):
        LOG.info('Scratch Link BLEAK listening on wss://%s:%s/scratch/ble', HOSTNAME, PORT)
        await asyncio.Future()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
