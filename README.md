# HA Sesame BLE

<p align="center">
  <img src="custom_components/sesame_ble/brand/icon.png" alt="HA Sesame BLE icon" width="180">
</p>

[![GitHub Release](https://img.shields.io/github/v/release/bingxyz/ha-sesame-ble?color=ff336c)](https://github.com/bingxyz/ha-sesame-ble/releases)
[![CI](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/ci.yml/badge.svg)](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/ci.yml)
[![Validate](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/validate.yml/badge.svg)](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5)](https://www.hacs.xyz/docs/faq/custom_repositories/)
[![License](https://img.shields.io/badge/license-MIT-29b6ff)](LICENSE)

[English](README.md) | [日本語](README.ja.md) | [繁體中文](README.zh-TW.md)

`ha-sesame-ble` is a Home Assistant custom integration that controls CANDY
HOUSE SESAME smart locks directly while keeping ESP32 devices as standard,
replaceable Bluetooth proxies—no SESAME-specific ESPHome component or firmware
is required.

This design is useful even with only one ESP32. Home Assistant owns the SESAME
authentication, encryption, state and command logic; the ESP32 provides only
generic BLE transport and can continue serving other Bluetooth devices.

Version `0.1.x` supports **SESAME 5 Pro only** and can connect through a local
Bluetooth adapter or an ESPHome Bluetooth proxy.

> [!IMPORTANT]
> The first implementation is complete, covered by automated tests, and has
> been validated with a physical SESAME 5 Pro through an ESPHome Bluetooth
> proxy. Proxy failover and longer-term operation still need validation.

## ✅ Supported models

| Model | Status |
| --- | --- |
| SESAME 5 Pro | Supported and tested with physical hardware |
| SESAME 5 | Not enabled in `0.1.x`; the underlying library supports it, but this integration has not validated it |
| SESAME 5 US | Not enabled in `0.1.x`; the underlying library supports it, but this integration has not validated it |
| SESAME 6 family and all other CANDY HOUSE products | Not supported |

The integration intentionally rejects Bluetooth discovery from every model
except SESAME 5 Pro. Related models will not appear in the setup flow merely
because they share the CANDY HOUSE Bluetooth service UUID. Support will be
enabled model by model only after protocol and hardware validation.

## 🔐 Why this project exists

The core goal is to keep SESAME-specific logic in Home Assistant instead of
turning an ESP32 into a dedicated lock controller:

- use an ordinary ESPHome Bluetooth proxy without custom components
- update, test and debug the integration without recompiling or flashing an
  ESP32
- keep credentials, device state, automations and backup/restore workflows
  centered in Home Assistant
- reuse the same ESP32 for other Bluetooth devices
- replace the ESP32 without migrating SESAME-specific firmware or logic

In short, the ESP32 acts as a replaceable Bluetooth network adapter, not as the
lock controller.

The existing Home Assistant `sesame` integration is a legacy cloud-polling
integration for the original SESAME Lock and its Wi-Fi Access Point. It is not a
local BLE integration for SESAME 5 Pro.

The third-party `esphome-sesame3` project can control SESAME directly from one
ESP32, but the protocol session and lock-specific logic are then owned by that
ESP32. That approach can be useful without Home Assistant or when control logic
must run independently on the microcontroller; it is not required when Home
Assistant is already the center of the installation.

Support for multiple Bluetooth proxies is an additional benefit of keeping the
protocol in Home Assistant: all proxies share the same integration state, and
Home Assistant can select a fresh reachable BLE route after a disconnection.

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

## ✨ First release

- automatic SESAME 5 Pro Bluetooth discovery
- setup through the Home Assistant UI
- owner/manager share URL or 32-character secret-key input
- explicit lock and unlock actions
- lock state, jam indication and availability
- angle, battery percentage, battery voltage and Bluetooth signal strength sensors
- last Home Assistant operation result and end-to-end duration diagnostics
- bounded reconnect backoff and fresh Home Assistant BLE route selection after
  connection loss
- redacted diagnostics

## 📊 Entities

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

## 📦 Installation

The repository can be installed as a HACS custom repository:

1. Open **HACS** in Home Assistant.
2. Open the menu and select **Custom repositories**.
3. Add `https://github.com/bingxyz/ha-sesame-ble` with category
   **Integration**.
4. Open **Sesame BLE** in HACS and select **Download**.
5. Restart Home Assistant.
6. Leave a connectable Bluetooth adapter or ESPHome Bluetooth proxy in range.
   Home Assistant will discover a supported SESAME 5 Pro automatically.

HACS installs integrations under the Home Assistant configuration directory's
`custom_components/` folder. Future releases can be installed and upgraded
from the same HACS repository entry.

The `v0.1.0` manifest installs `gomalock` 2.2.0 from an immutable commit in the
maintained [`bingxyz/gomalock`](https://github.com/bingxyz/gomalock) fork. That
fork adds Home Assistant BLE routing and disconnect hooks on top of the original
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

During setup, provide exactly one of:

- an owner/manager `ssm://` share URL; or
- the lock's 32-character hexadecimal secret key.

Credentials are verified by making a real encrypted BLE login before the config
entry is saved.

## 🧭 Project boundaries

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

## 🔗 References

- [CANDY HOUSE API documentation](https://github.com/CANDY-HOUSE/API_document)
- [gomalock upstream](https://github.com/meronepy/gomalock)
- [gomalock HA transport fork](https://github.com/bingxyz/gomalock)
- [esphome-sesame3](https://github.com/homy-newfs8/esphome-sesame3)
- [Home Assistant Bluetooth developer documentation](https://developers.home-assistant.io/docs/bluetooth/)
- [Home Assistant Bluetooth APIs](https://developers.home-assistant.io/docs/core/bluetooth/api/)
- [Existing Home Assistant Sesame integration](https://www.home-assistant.io/integrations/sesame/)
