# RC-only fuzz testing

See the [illustrated RC fuzzing process and verified rollout results](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/rc-fuzzing-results.md)
for the shared release flow, evidence requirements and a dated cross-project
snapshot. The project-specific scope and reproduction guidance below still apply.

Targets exercise the actual in-memory TAR payload parser through its bounded gzip reader and pure release identity validator. They mutate synthetic archives and metadata, checking confined payload names and digests. No target calls SSH, installs a payload, executes device commands or starts a hardware qualification.

Each target receives a 60-second mutation budget and at most 4,096 input bytes.
The pinned shared release workflow runs Atheris 3.1.0 on Python 3.12 only for
an explicit RC on the public default branch. PR, push, beta, nightly and stable
runs do not start mutation campaigns. Ordinary tests retain deterministic regressions.

The archive harness recomputes gzip transport bytes after each mutation so inputs
reach the owned TAR traversal and payload checks. Existing deterministic tests
cover compressed expansion limits; this campaign does not claim to fuzz gzip itself.

## Reproduce and investigate

On supported Linux x86-64, create `.fuzz-venv` with Python 3.12 and install
`.github/requirements-fuzz.txt` using `pip install --require-hashes --only-binary=:all:`.
The exact target commands and seed directories are in `.github/fuzz.json`; append
`-max_total_time=60 -timeout=10 -rss_limit_mb=2048` for a bounded local run.
Run a saved input file instead of a corpus directory to reproduce one failure.

The shared runner additionally removes network access during each campaign,
limits process resources, and binds its report and validation receipt to the
repository, source commit, workflow attempt and manifest. A zero-execution or
failed campaign cannot qualify the RC. Diagnose the failure, reduce a synthetic
input, add a regression and repeat the RC without suppressing the oracle.

Only invented payloads and documentation addresses belong in the seed corpus.
Never add real device backups, credentials, household data or private captures.
The README badge describes this RC-only capability; it is not OSS-Fuzz enrollment
or proof of hardware, firmware or deployed-system acceptance.

## Source distribution

`release-files.json` is the reviewed exact inventory. Beta and RC archives carry
`SOURCE_VERSION`, are checked after extraction in a temporary directory, and
have frozen version receipts and checksums. See [RELEASING.md](../RELEASING.md)
for the release procedure. Hardware qualification and deployment remain separate.


## Deterministic preflight in ordinary CI

For relevant changes in a public repository, the existing CI configuration
contract job installs the hash-locked Python 3.12 fuzz dependencies, runs
`pip check`, and replays the committed corpus with Atheris `-runs=0`.
This is deterministic seed replay: it does not start the timed mutation
campaign. Timed fuzzing remains exclusive to release candidates. The shared
preflight has a four-minute total budget, including dependency setup.

The `preflight-paths` entries in `.github/fuzz.json` select the relevant
production, dependency and harness changes. Shared contract, manifest and
workflow changes also trigger this check; missing comparison history runs
the check conservatively. Unrelated changes can skip this extra replay.

Before replay, the shared helper verifies that the following declarations
refer to project-local Python functions already instrumented by the
harness. Missing import instrumentation fails the check instead of
silently counting executions with incomplete feedback:

- `hardware.device_runner.validate_release_artifact`
- `hardware.device_runner._validate_release_files`
- `hardware.release_artifact._archive_payload`

Update these declarations when production functions move or are renamed.
They prove that the selected code is instrumented; they do not prove
exhaustive path coverage. Keep positive and rejected-input corpus cases
and independent semantic assertions alongside the existing unit tests.

## Release workflow retries

Fresh release inputs are selected by the exact GitHub workflow run ID and run
attempt. After a failed or partial run, choose **Re-run all jobs** so every
required producer creates inputs for the same attempt. Retrying only failed jobs
or an individual job intentionally fails when a complete current-attempt input
set is missing.

Artifacts from older attempts may remain available for diagnostics; they are not
inputs to the new attempt and do not need to be deleted. Filtering artifact names
alone does not prove package completeness or receipt identity. Complete package
inventory and receipt identity checks remain separate release requirements.

See the shared [package identity and retry contract](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/VERSIONING.md#package-identity-across-reruns).
