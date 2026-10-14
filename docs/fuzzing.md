# RC-only fuzz testing

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
