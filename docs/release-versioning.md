# Release version files

The release policy owns `SOURCE_VERSION`, `pyproject.toml` and the local
`integration-tests` package version in `uv.lock`.

Use `python3 scripts/release.py prepare-version --bump next-patch --pr`
to prepare a release. The shared version planner updates these files together.
Dependency versions and hashes in `uv.lock` remain unchanged. CI verifies the
committed base versions before the beta → RC → stable release chain.
