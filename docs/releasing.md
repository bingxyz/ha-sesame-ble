# Releasing

Releases are intentional and use a release pull request as the approval point.
Merging a version increase into `main` publishes the release automatically.

## Prepare and publish a release

1. Create a `release/vX.Y.Z` branch from the latest `main`.
2. Increase the version in:
   - `custom_components/sesame_ble/manifest.json`
   - `pyproject.toml`
   - `uv.lock`
3. Open a pull request and wait for CI, HACS and Hassfest to pass.
4. Merge the pull request into `main`.

Changing any of the three version files on `main` starts the Release workflow.
The workflow verifies that all versions match and that the version increased,
runs the complete test and static-analysis suite, confirms that `main` did not
move during validation, and creates the Git tag and GitHub Release with
generated release notes.

No separate publish button or local `git tag` command is required.

## Recovery

If automatic publishing fails before the tag is created, open
**Actions → Release → Run workflow**, select `main`, and run it again. The
workflow reads the version from the repository. If that tag already exists, the
manual run exits successfully without publishing a duplicate release.

HACS discovers the new GitHub Release automatically. Users can then update the
integration from HACS and restart Home Assistant.
