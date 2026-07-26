# Releasing

Releases are intentional and start only from the GitHub Actions interface.
Merging into `main` never publishes a new version automatically.

## Prepare the release

1. Create a `release/vX.Y.Z` branch from the latest `main`.
2. Update the version in:
   - `custom_components/sesame_ble/manifest.json`
   - `pyproject.toml`
   - `uv.lock`
3. Open a pull request and wait for CI, HACS and Hassfest to pass.
4. Merge the pull request into `main`.

## Publish the release

1. Open **Actions → Release → Run workflow** on GitHub.
2. Select the `main` branch.
3. Enter the version without the `v` prefix, such as `0.1.3`.
4. Run the workflow.

The workflow verifies that all three version files match, rejects an existing
tag, runs the complete test and static-analysis suite, confirms that `main` did
not move during validation, and creates the Git tag and GitHub Release with
generated release notes.

HACS discovers the new GitHub Release automatically. Users can then update the
integration from HACS and restart Home Assistant.
