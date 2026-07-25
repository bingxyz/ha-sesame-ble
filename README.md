# HA Sesame BLE

`ha-sesame-ble` is a Home Assistant custom integration for local Bluetooth
control of CANDY HOUSE SESAME smart locks.

The initial target is SESAME 5 Pro. Home Assistant owns the SESAME protocol
session and connects through any reachable connectable Bluetooth adapter,
including ESPHome Bluetooth proxies.

> [!IMPORTANT]
> The first implementation is complete, covered by automated tests, and has
> been validated with a physical SESAME 5 Pro through an ESPHome Bluetooth
> proxy. Proxy failover and longer-term operation still need validation.

## Why this project exists

The existing Home Assistant `sesame` integration is a legacy cloud-polling
integration for the original SESAME Lock and its Wi-Fi Access Point. It is not a
local BLE integration for SESAME 5 Pro.

The third-party `esphome-sesame3` project can control SESAME directly from one
ESP32, but the protocol session is then owned by that ESP32. Other Bluetooth
proxies cannot take over if that ESP32 goes offline.

This project instead keeps ordinary ESPHome Bluetooth proxies interchangeable:

```text
SESAME 5 Pro
    ↕ BLE
any reachable ESPHome Bluetooth proxy
    ↕ ESPHome API / network
Home Assistant + ha-sesame-ble
```

On the ESPHome side, only a standard connectable proxy is required:

```yaml
esp32_ble_tracker:

bluetooth_proxy:
  active: true
```

The YAML only provides BLE transport. Authentication, encryption, state and
lock commands are implemented by this Home Assistant integration using the
`gomalock` Python library.

## First release

- automatic SESAME 5 Pro Bluetooth discovery
- setup through the Home Assistant UI
- owner/manager share URL or 32-character secret-key input
- explicit lock and unlock actions
- lock state, jam indication and availability
- angle, battery percentage, battery voltage and Bluetooth signal strength sensors
- bounded reconnect backoff and fresh Home Assistant BLE route selection after
  connection loss
- redacted diagnostics

## Entities

| Entity | Default | Description |
| --- | --- | --- |
| Lock | enabled | Locked/unlocked state plus lock and unlock commands |
| Angle | enabled | Current mechanical angle in degrees |
| Battery | enabled | Estimated battery percentage |
| Battery voltage | disabled | Raw voltage reported by the lock |
| Signal strength | disabled | RSSI from the latest connectable BLE advertisement |
| Last HA operation result | disabled | Success or failure of the last HA command |
| Last HA operation duration | disabled | End-to-end duration of the last HA command |
| Low battery | disabled | SESAME low-battery flag |

State comes from SESAME mechanical-status notifications. If the lock is outside
its calibrated lock and unlock ranges, the lock state is unknown while the angle
sensor still reports its position.

Signal strength is diagnostic data from the latest advertisement received by
Home Assistant or an ESPHome Bluetooth proxy. It is not a live measurement from
the persistent GATT connection and may remain unchanged while the lock is
connected.

Operation diagnostics cover only commands sent by Home Assistant. Duration
includes any required reconnect and login time. A successful result means the
command was accepted by SESAME; mechanical failure is still reported through
the lock entity's jammed state.

## Installation status

The repository has the structure required by HACS. During hardware testing, the
manifest installs `gomalock` 2.2.0 from an immutable commit in the maintained
[`bingxyz/gomalock`](https://github.com/bingxyz/gomalock) fork. That fork adds
Home Assistant BLE routing and disconnect hooks on top of the original
[`meronepy/gomalock`](https://github.com/meronepy/gomalock) project. This can
later switch back to a PyPI release if the transport hooks are accepted
upstream.

For local development, the sibling `../gomalock` checkout is used directly:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy custom_components
```

After this repository is hosted on GitHub, add it as a HACS custom repository,
install **Sesame BLE**, restart Home Assistant, and leave at least one
connectable Bluetooth adapter or ESPHome proxy in range. The integration will
appear in the discovered integrations list when it sees a SESAME 5 Pro.

During setup, provide exactly one of:

- an owner/manager `ssm://` share URL; or
- the lock's 32-character hexadecimal secret key.

Credentials are verified by making a real encrypted BLE login before the config
entry is saved.

## Project boundaries

- `ha-sesame-ble` is the Home Assistant integration and is maintained as this
  project's primary deliverable.
- `gomalock` remains an independent protocol library. This workspace contains a
  backward-compatible transport extension for Home Assistant routing.
- `esphome-sesame3` and `libsesame3bt` are useful references, but are not runtime
  dependencies of this architecture.
- SESAME history synchronization and support for older SESAME OS2 products are
  outside the first release.

See [Research and design](docs/research-and-design.md) for the full analysis,
decisions, risks and implementation plan.

## References

- [CANDY HOUSE API documentation](https://github.com/CANDY-HOUSE/API_document)
- [gomalock upstream](https://github.com/meronepy/gomalock)
- [gomalock HA transport fork](https://github.com/bingxyz/gomalock)
- [esphome-sesame3](https://github.com/homy-newfs8/esphome-sesame3)
- [Home Assistant Bluetooth developer documentation](https://developers.home-assistant.io/docs/bluetooth/)
- [Home Assistant Bluetooth APIs](https://developers.home-assistant.io/docs/core/bluetooth/api/)
- [Existing Home Assistant Sesame integration](https://www.home-assistant.io/integrations/sesame/)
