# Research and design

## 1. Objective

Build a local Home Assistant custom integration that controls a SESAME 5 Pro
through Home Assistant's Bluetooth stack and standard ESPHome Bluetooth proxies.

The defining requirement is that no single ESP32 owns the lock protocol. If one
proxy disappears, a later connection attempt must be able to use another proxy
that can reach the same lock.

The project is unofficial and must not imply endorsement or support from CANDY
HOUSE or Home Assistant.

## 2. Desired architecture

```text
                         ┌─ ESP32 proxy A ─┐
                         ├─ ESP32 proxy B ─┤
SESAME 5 Pro ← Bluetooth ├─ ESP32 proxy C ─┼→ Home Assistant Bluetooth
                         ├─ ESP32 proxy D ─┤            ↓
                         └─ ESP32 proxy E ─┘      ha-sesame-ble
                                                        ↓
                                                   lock entity
```

Responsibilities are deliberately separated:

| Layer | Responsibility |
| --- | --- |
| SESAME 5 Pro | Mechanical lock and SesameOS3 GATT server |
| ESPHome proxy | Generic scanning and connectable BLE transport |
| Home Assistant Bluetooth | Adapter discovery, routing and connection-slot management |
| `gomalock` | SesameOS3 packets, authentication, crypto and commands |
| `ha-sesame-ble` | Configuration, lifecycle, entities, availability and retry policy |

The proxies contain no SESAME UUID, secret key or SESAME-specific component.
They only require `bluetooth_proxy.active: true`.

## 3. Sources reviewed

### 3.1 Official CANDY HOUSE material

The local workspace contains the official `API_document` and
`SesameSDK_ESP32_with_DemoApp` repositories.

Relevant confirmed protocol facts:

- SESAME 5 Pro is a SesameOS3 product; its advertised model value is `7`.
- SESAME BLE service UUID is `0xFD81`.
- GATT write-without-response characteristic is
  `16860002-a5ae-9856-b6d3-dbb4c676993e`.
- GATT notify characteristic is
  `16860003-a5ae-9856-b6d3-dbb4c676993e`.
- Advertisement manufacturer data contains the model, registration flag and
  stable SESAME device UUID.
- Registration uses ECDH on `secp256r1`; the first 16 bytes of the shared secret
  become the device secret.
- Login derives an AES-CMAC session value from the device secret and the
  per-connection random/session token.
- Commands after login are session-encrypted, so moving an active session from
  one BLE connection to another is not possible. Failover means reconnecting and
  logging in again.

### 3.2 Existing Home Assistant `sesame` integration

The integration at <https://www.home-assistant.io/integrations/sesame/> is not
the implementation needed here.

- It supports the original SESAME Lock rather than SESAME 5 Pro BLE.
- It requires the standalone Wi-Fi Access Point and API key.
- Its IoT class is cloud polling.
- The documentation directs current SESAME 5 plus Hub 3 users toward Matter.

Matter through Hub 3 is a valid alternative for local control, but Hub 3 becomes
the dedicated bridge. It does not make multiple ESPHome Bluetooth proxies
interchangeable.

### 3.3 `esphome-sesame3`

`homy-newfs8/esphome-sesame3` is a capable ESPHome external component. It wraps
the author's `libsesame3bt` C++ library and supports many SESAME OS2 and OS3
models, including SESAME 5 Pro.

It demonstrates useful behavior and protocol interpretations:

- UUID and secret-key configuration for SesameOS3 products
- persistent connections for lock entities
- lock state and battery exposure
- history tags and history-related sensors
- reconnect handling and unknown-state handling
- multiple SESAME connections from one ESP32

It intentionally owns BLE and the Sesame session on the ESP32. Its documentation
states that it does not use ESPHome's built-in `BTClient` and cannot coexist with
other BLE components on the same ESP32. Its component also declares a conflict
with ESPHome's `esp32_ble` component.

NimBLE is used because the implementation needs direct BLE central control,
asynchronous GATT connections, configurable simultaneous-connection limits and
lower embedded resource usage. This is appropriate for an ESP32-native Sesame
client, but it prevents that ESP32 from remaining an ordinary Home Assistant BLE
proxy in the desired architecture.

Consequently:

- `esphome-sesame3` can control the lock successfully.
- The specific ESP32 running it becomes the lock controller.
- Other generic proxies cannot take over its authenticated Sesame session.
- It remains a valuable behavior/reference implementation, not a runtime
  dependency for `ha-sesame-ble`.

Related repositories have different roles:

- `libsesame3bt`: reusable C++ Sesame BLE protocol/client library for ESP32.
- `esphome-sesame3`: ESPHome entities and configuration around `libsesame3bt`.
- `esphome-sesame_server`: ESPHome support for SESAME peripherals/relay-style
  scenarios; it is not required for direct HA-to-lock BLE control.

### 3.4 `gomalock`

`meronepy/gomalock` version 2.1.0 is a typed asynchronous Python BLE library,
licensed under MIT and requiring Python 3.12 or newer. Runtime dependencies are
Bleak and PyCryptodome.

It supports:

- SESAME 5, SESAME 5 Pro and SESAME 5 US
- lock, unlock and toggle
- mechanical position and target
- locked/unlocked range flags and motor stop state
- battery voltage, battery percentage and critical-battery flag
- lock/unlock position settings
- auto-lock duration
- firmware version
- new-device registration
- owner/manager QR URL parsing/generation at the protocol level
- unexpected-disconnect detection and bounded reconnect attempts
- Sesame Touch-family status support

History retrieval is not implemented. This is acceptable for the first Home
Assistant release.

The codebase contains approximately 166 unit tests covering the transport,
protocol, cipher, scanner and device classes. Static inspection found a clear
separation between BLE transport and SesameOS3 protocol, making adaptation
practical without rewriting crypto or command handling.

## 4. Why `gomalock` does not work with HA proxies unchanged

The current transport performs these operations internally:

1. Start a new `BleakScanner`.
2. Resolve an address into a `BLEDevice`.
3. Cache the scanned object in `_identifier`.
4. Construct a raw `BleakClient`.
5. Connect, subscribe to notifications and write GATT packets.

This conflicts with Home Assistant Bluetooth best practices:

- integrations should use HA's shared scanner instead of starting another one;
- a connectable `BLEDevice` should be obtained through HA's Bluetooth APIs;
- transient connection failures should use `bleak-retry-connector`;
- a `BleakClient` should not be reused across separate connections.

The cached `BLEDevice` is especially important. In Home Assistant it includes
backend details for the local adapter or remote ESPHome proxy that produced it.
If proxy A supplied the first object and later goes offline, reusing that object
does not guarantee a route through proxy B.

Correct failover requires this sequence for every new connection attempt:

```text
connection lost
      ↓
discard old BleakClient and BLEDevice
      ↓
ask Home Assistant for a currently connectable route
      ↓
create a new client through that route
      ↓
receive new session token and log in again
      ↓
retry operation when safe
```

This is reconnect-and-reauthenticate failover, not seamless migration of an
existing GATT connection.

## 5. Proposed backward-compatible `gomalock` extension

The library should continue working unchanged for ordinary users:

```python
Sesame5(address, secret_key=secret)
```

Home Assistant needs optional injected transport hooks. The exact public API is
still to be finalized, but the intended boundary is similar to:

```python
Sesame5(
    address_or_device,
    secret_key=secret,
    ble_device_resolver=resolver,
    connection_factory=connection_factory,
)
```

Required behavior:

1. A resolver supplied by the caller is invoked on every fresh connection.
2. The previous `BLEDevice` is not reused after disconnection.
3. A connection factory may return an already-connected Bleak-compatible client.
4. Default resolver and client behavior remain the current Bleak implementation.
5. Notification, disconnect and GATT interfaces remain protocol-agnostic.
6. Existing public constructors and examples remain compatible.
7. New unit tests prove resolver refresh and client replacement during reconnect.

For Home Assistant, the resolver will call
`bluetooth.async_ble_device_from_address(..., connectable=True)`, while the
connection factory will use `bleak-retry-connector`.

Avoid implementing this by importing `gomalock` private modules or monkeypatching
its global `BleakClient`. That would make the integration fragile across library
updates.

The change should first be developed on a local feature branch. After real-device
validation it can either be proposed upstream or maintained in a fork. The HA
integration should ultimately depend on a released, reproducible package version
rather than a permanent Git URL.

## 6. Home Assistant integration design

### 6.1 Domain and packaging

Use the new domain `sesame_ble`. Do not reuse `sesame`, because that domain is
already owned by Home Assistant's legacy cloud integration.

Initial repository layout:

```text
ha-sesame-ble/
├── custom_components/
│   └── sesame_ble/
│       ├── __init__.py
│       ├── config_flow.py
│       ├── const.py
│       ├── diagnostics.py
│       ├── lock.py
│       ├── manifest.json
│       ├── runtime.py
│       ├── strings.json
│       └── translations/
│           └── zh-Hant.json
├── docs/
├── tests/
├── hacs.json
├── pyproject.toml
└── README.md
```

### 6.2 Discovery and identity

The manifest can discover connectable advertisements using:

- service UUID `0000fd81-0000-1000-8000-00805f9b34fb`;
- CANDY HOUSE manufacturer ID `0x055A` (`1370` decimal);
- `connectable: true`.

The stable SESAME device UUID from manufacturer data should be the config-entry
unique ID. BLE address should be treated as a current transport locator, not the
primary user-facing identity.

The first release should filter the advertised model to SESAME 5 Pro (`7`) even
though the underlying library supports related models. More models can be enabled
after the lifecycle has been validated.

### 6.3 Configuration

Preferred setup flow:

1. Home Assistant discovers a SESAME 5 Pro.
2. User confirms the discovered device.
3. User pastes an owner or manager share QR URL from the official app.
4. Integration parses and validates model, UUID and 16-byte secret key.
5. Integration attempts a connection and login before creating the entry.

Manual UUID plus secret-key input can be offered as a fallback.

An already registered lock should not be registered again. Registration changes
device ownership state and belongs outside the normal first-release setup path.

The secret key is sensitive:

- never log it;
- redact it from diagnostics;
- never expose it as an entity attribute;
- store only what is required in config-entry data;
- use a manager key where practical instead of the owner key.

### 6.4 Runtime ownership

One runtime object per config entry should own:

- the `gomalock.Sesame5` instance;
- an operation lock to serialize connect/login/lock/unlock work;
- current mechanical and battery status;
- the current Bleak client and connection generation;
- reconnect task and bounded backoff;
- entity update callbacks;
- unload/shutdown cleanup.

The HA integration should own high-level retry policy. `gomalock`'s internal
background reconnect should initially be disabled (`reconnect_attempts=0`) to
avoid two independent reconnect loops racing each other.

### 6.5 Entities

First release:

- one `LockEntity` using in-memory mechanical status;
- battery percentage as a device-class battery sensor or lock attribute, with a
  separate sensor preferred for normal HA behavior;
- optional battery voltage and connection diagnostics after the base entity is
  stable.

Entity properties must not perform BLE I/O. Callbacks update cached state and
schedule HA state writes.

Possible state mapping:

| Sesame status | Home Assistant state |
| --- | --- |
| in lock range, motor stopped | locked |
| in unlock range, motor stopped | unlocked |
| motor moving toward lock | locking |
| motor moving toward unlock | unlocking |
| clutch/critical mechanical failure | jammed where semantically valid |
| connected but outside both calibrated ranges | unknown or unlocked only after explicit policy decision |
| disconnected with stale state | unavailable or last-known state with explicit availability false |

The ambiguous-position and jammed mappings require real-device traces before
being finalized.

## 7. Connection strategy

### 7.1 Persistent connection

Advantages:

- immediate manual-turn updates;
- low command latency;
- current battery and mechanical status;
- matches `esphome-sesame3`'s requirement for a lock entity.

Costs:

- consumes a Bluetooth proxy connection slot;
- may contend with the official mobile app;
- requires robust reconnect and failover behavior;
- could affect lock battery life and must be measured.

### 7.2 On-demand connection

Advantages:

- no permanent proxy slot consumption;
- less likely to block the official app.

Costs:

- state becomes stale after disconnect;
- manual lock turns are not immediately visible;
- every command pays scan, connect and login latency;
- periodic polling may be worse for reliability or battery than a stable
  connection.

### 7.3 Initial decision

Start the proof of concept with a persistent connection because accurate lock
state is a core Home Assistant expectation. Measure official-app coexistence,
proxy slot usage, reconnect latency and battery behavior. If necessary, expose
an advanced connection-mode option later; do not add it before there is data to
support both modes.

## 8. Multi-proxy behavior and limits

Expected failover behavior:

1. The active proxy or its network path fails.
2. Bleak reports disconnection; entity becomes temporarily unavailable.
3. Runtime discards all connection-specific state.
4. After bounded backoff, it asks HA for a fresh connectable `BLEDevice`.
5. HA returns a route from a currently reachable adapter/proxy.
6. Runtime creates a new client, receives a new session token and logs in.
7. Entity becomes available and receives fresh mechanical state.

This does remove the dedicated Sesame ESP32 as a single point of failure, but it
does not guarantee zero interruption. Recovery time includes HA noticing proxy
loss, retry backoff, BLE connection and Sesame login.

Additional limits:

- At least one active/connectable proxy must be within BLE range.
- A proxy needs a free connection slot.
- If the strongest visible proxy is online but consistently fails to connect,
  retries may need explicit candidate iteration using HA's per-adapter discovery
  information instead of repeatedly selecting the same route.
- A command interrupted after transmission has an uncertain result. Automatic
  replay must be conservative: first reconnect and refresh state, then decide
  whether replay is still required. Blindly replaying toggle is unsafe; explicit
  lock/unlock commands are safer because they are idempotent at the desired-state
  level.

## 9. Validation plan

### Phase 0: library transport tests

- inject a fake resolver and connection factory;
- prove the resolver is called for each connection;
- prove a disconnected client is not reused;
- prove existing constructor behavior remains unchanged;
- run all existing `gomalock` tests.

### Phase 1: hard-coded proof of concept

- one SESAME 5 Pro;
- one ESPHome active proxy;
- hard-coded development UUID and secret outside Git;
- connect, login, obtain mechanical status, lock and unlock;
- record timings and BLE logs without secrets.

### Phase 2: failover proof

- expose the lock to at least two active proxies;
- establish a connection through proxy A;
- power off or disconnect proxy A;
- verify a new `BLEDevice` is acquired through proxy B;
- verify new login, state refresh and control;
- repeat during idle, during login and during a lock command.

### Phase 3: Home Assistant product surface

- Bluetooth discovery and config flow;
- QR/manual-key validation;
- lock and battery entities;
- availability and unload behavior;
- translations and diagnostics;
- config-entry reload and HA restart tests.

### Phase 4: release hardening

- unit tests with mocked Home Assistant Bluetooth backends;
- failure injection for timeout, no slot, proxy loss and bad key;
- HACS metadata and installation documentation;
- secret redaction review;
- compatibility testing against supported HA releases;
- decide whether the `gomalock` work is an upstream PR or maintained fork.

## 10. Difficulty and estimate

| Work area | Difficulty | Reason |
| --- | --- | --- |
| SesameOS3 crypto and commands | low | already implemented and tested in `gomalock` |
| HA lock entity and config entry | low | standard Home Assistant patterns |
| Bluetooth discovery | medium | advertisement parsing exists; HA wiring is required |
| Proxy-aware transport adaptation | medium | small code surface but API boundary matters |
| reliable multi-proxy recovery | medium-high | stale routes, slots and interrupted operations |
| production state/availability behavior | medium-high | requires real-device observation |

Estimated effort for one experienced Python/HA developer:

- basic proxy-based proof of concept: 1-2 days;
- usable MVP: 4-7 working days;
- stable HACS-quality release: approximately 2-3 weeks;
- Home Assistant Core submission, if desired: additional quality-scale work and
  review time.

The protocol library has already removed most of the cryptographic risk. The
remaining work is primarily lifecycle and reliability engineering.

## 11. Decisions already made

- Create a separate `ha-sesame-ble` repository.
- Use the `sesame_ble` domain, not the existing `sesame` domain.
- Make this project the primary maintained deliverable.
- Keep `gomalock` independent and modify it backward-compatibly.
- Decide upstream PR versus maintained fork after real-device validation.
- Use standard ESPHome active Bluetooth proxies; do not deploy
  `esphome-sesame3` on the proxy ESP32s.
- Target SESAME 5 Pro first.
- Obtain credentials from an owner/manager share QR rather than registering an
  already-used lock.
- Let HA own high-level reconnection policy.
- Re-resolve the BLE route on every new connection.

## 12. Open questions requiring implementation or hardware evidence

- Does a persistent HA connection prevent or disrupt the official mobile app on
  the tested SESAME 5 Pro firmware?
- How many simultaneous connections are actually available on each deployed
  ESPHome proxy configuration?
- How quickly does HA remove a failed proxy route and select another one?
- Does the nearest-route helper sufficiently avoid a flaky-but-visible proxy, or
  is explicit candidate iteration necessary?
- What exact publish sequence occurs after login on the user's firmware?
- How should intermediate angle, clutch failure and motor direction map to HA
  lock states?
- What retry policy provides fast recovery without excessive BLE traffic or
  lock battery drain?
- Should battery voltage and firmware version be separate diagnostic entities in
  the first public release or a later release?

These questions should be answered with captured behavior and tests, not by
adding speculative options before the proof of concept.
