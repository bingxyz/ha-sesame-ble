# HA Sesame BLE

`ha-sesame-ble` is an experimental Home Assistant custom integration for local
Bluetooth control of CANDY HOUSE SESAME smart locks.

The initial target is SESAME 5 Pro. Home Assistant owns the SESAME protocol
session and connects through any reachable connectable Bluetooth adapter,
including ESPHome Bluetooth proxies.

> [!IMPORTANT]
> This project is currently in the design phase. It does not control a lock yet.

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

## Planned first release

- SESAME 5 Pro Bluetooth discovery
- setup through the Home Assistant UI
- owner/manager QR URL or UUID plus secret-key input
- lock and unlock actions
- lock state, battery level and availability
- connection retry through ESPHome Bluetooth proxies
- selection of another reachable proxy after connection loss
- diagnostics with secrets redacted

## Project boundaries

- `ha-sesame-ble` is the Home Assistant integration and is maintained as this
  project's primary deliverable.
- `gomalock` remains an independent protocol library. It needs a small,
  backward-compatible transport extension for Home Assistant.
- `esphome-sesame3` and `libsesame3bt` are useful references, but are not runtime
  dependencies of this architecture.
- SESAME history synchronization and support for older SESAME OS2 products are
  outside the first release.

See [Research and design](docs/research-and-design.md) for the full analysis,
decisions, risks and implementation plan.

## References

- [CANDY HOUSE API documentation](https://github.com/CANDY-HOUSE/API_document)
- [gomalock](https://github.com/meronepy/gomalock)
- [esphome-sesame3](https://github.com/homy-newfs8/esphome-sesame3)
- [Home Assistant Bluetooth developer documentation](https://developers.home-assistant.io/docs/bluetooth/)
- [Home Assistant Bluetooth APIs](https://developers.home-assistant.io/docs/core/bluetooth/api/)
- [Existing Home Assistant Sesame integration](https://www.home-assistant.io/integrations/sesame/)

