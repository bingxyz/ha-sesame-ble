# Repository guidance for coding agents

This file applies to the entire repository.

## Product and architecture contract

- This project is a Home Assistant custom integration for local BLE control of
  CANDY HOUSE SESAME locks.
- Home Assistant owns SESAME credentials, authentication, encryption, state,
  retries and commands. ESP32 devices remain standard, replaceable ESPHome
  Bluetooth proxies.
- Do not move SESAME protocol or lock-control logic into ESPHome firmware and do
  not require a SESAME-specific ESPHome component.
- Use Home Assistant's Bluetooth APIs and the transport injection in
  `custom_components/sesame_ble/bluetooth.py`. Do not bypass Home Assistant
  routing with a directly constructed Bleak client; that would break local
  adapter/proxy selection and failover.
- `custom_components/sesame_ble/runtime.py` owns the persistent authenticated
  session, serialized operations, reconnect loop and cached entity state.
  `gomalock` owns the SESAME protocol implementation. Avoid duplicating protocol
  parsing or cryptography in this repository.
- Lock commands express a desired final state. Never blindly replay a command
  after an ambiguous disconnect because the first command may already have
  reached the physical lock.

## Supported hardware

- The currently enabled and physically validated model is **SESAME 5 Pro**.
  `SUPPORTED_MODEL` in `custom_components/sesame_ble/const.py` is the discovery
  gate.
- Do not enable SESAME 5, SESAME 5 US, SESAME 6-family devices or accessories
  solely because they share service UUIDs or appear supported by `gomalock`.
- A model may be advertised as supported only after protocol review, automated
  coverage and physical-device validation. Clearly label unverified behavior as
  experimental.

## `gomalock` dependency

- Local development uses the editable sibling checkout at `../gomalock`, as
  configured in `pyproject.toml`.
- Home Assistant installs the pinned fork archive from
  `custom_components/sesame_ble/manifest.json`.
- CI and release workflows check out the same fork commit before `uv sync`.
- When changing the pinned `gomalock` revision, keep the manifest requirement
  and every workflow checkout ref synchronized, update `uv.lock` if needed, and
  run the complete test suite.
- Do not switch back to the upstream PyPI package until it contains the required
  Home Assistant BLE transport and disconnect hooks.
- Changes to the sibling `gomalock` repository require their own branch,
  tests and review; do not silently mix them into this repository's commit.

## Home Assistant implementation rules

- Target Python 3.14 and follow current Home Assistant async APIs.
- Never perform blocking BLE or filesystem I/O on the Home Assistant event loop.
- Keep one runtime in `ConfigEntry.runtime_data`; entities should expose cached
  state and subscribe to runtime listeners.
- Preserve config-entry unique IDs, entity unique IDs and translation keys.
  Introduce an explicit migration before changing persisted identifiers or the
  config-flow schema.
- Treat an entity as available only when the integration has a usable,
  authenticated session, unless the entity intentionally preserves a completed
  diagnostic value.
- New secondary telemetry and diagnostic entities should normally be disabled
  by default. Prefer standard Home Assistant device classes, state classes and
  units.
- Do not add custom services when a standard Home Assistant entity API already
  represents the operation.

## Security and privacy

- Never log, commit, snapshot or expose a secret key or SESAME share URL.
- Treat device UUIDs, Bluetooth addresses and household activity timestamps as
  private in public screenshots and issue examples; redact them unless they are
  synthetic.
- Keep credential form fields password-masked.
- Diagnostics must redact all credentials. Re-review
  `custom_components/sesame_ble/diagnostics.py` whenever config-entry data gains
  a new sensitive field.
- Test fixtures must use synthetic credentials and device identifiers.

## Translations and documentation

- `custom_components/sesame_ble/strings.json` is the source definition for
  config-flow and entity translations.
- Keep `translations/en.json`, `translations/ja.json` and
  `translations/zh-Hant.json` synchronized for every user-visible addition or
  state change.
- Keep `README.md`, `README.ja.md` and `README.zh-TW.md` aligned for material
  user-facing behavior, installation, compatibility and architecture changes.
- Do not put temporary test status or speculative roadmap items in this file.
  Use issues, pull requests or research documents for information that can
  become stale.

## Tests and required checks

- Add or update focused tests for behavior changes. Tests must not require a
  physical lock, Bluetooth adapter or live Home Assistant instance.
- Mock at the Home Assistant Bluetooth/transport boundary while preserving the
  runtime behavior being tested.
- Before proposing a change, run:

  ```bash
  uv sync --frozen
  uv run pytest
  uv run ruff check .
  uv run mypy custom_components
  ```

- `uv sync` expects the sibling `../gomalock` checkout. CI creates that layout
  automatically.
- Automated tests do not replace physical validation for new hardware support
  or BLE connection behavior. Report automated and physical test evidence
  separately.

## Git and releases

- Work on a focused branch and use a pull request. Do not push ordinary changes
  directly to `main`.
- Wait for CI, HACS and Hassfest checks before merging.
- Ordinary fixes and documentation changes do not bump the version.
- An intentional release updates the same semantic version in:
  - `custom_components/sesame_ble/manifest.json`
  - `pyproject.toml`
  - `uv.lock`
- Merging that version increase into `main` triggers
  `.github/workflows/release.yml`, which validates, tests, tags and creates the
  GitHub Release automatically.
- Do not manually create a tag or GitHub Release during the normal release
  path. Use the workflow's manual dispatch only to recover from an automatic
  release failure before the tag was created.
- Follow `docs/releasing.md` for the current release procedure.
