# Release artifacts and physical acceptance

A successful package build, a published stable tag and a hardware pass are three
different records. Keep all three tied to immutable artifact digests. The
Cerbo scenario here exercises inverter-control only; it does not operate or
qualify inverter-climate thermostats.

## Prepare a release binding without connecting to hardware

Read the exact release's metadata from GitHub, including each asset's SHA-256
digest. Download its application `.tar.gz` and `release-manifest.json`. Retain
that metadata separately and obtain the two digest arguments from it, rather
than computing new expected values from potentially substituted local files.
The builder verifies both independent pins, checks the manifest's asset digest
and size, and hashes every regular payload file without extracting or importing
the archive. Links, duplicate entries, traversal and oversized inputs fail.

From this repository root:

```sh
python3 -m hardware.release_artifact \
  --archive /path/to/inverter-control-VERSION.tar.gz \
  --manifest /path/to/release-manifest.json \
  --archive-sha256 EXPECTED_ARCHIVE_SHA256 \
  --manifest-sha256 EXPECTED_MANIFEST_SHA256 \
  --release-tag vVERSION \
  --output /path/to/new-release-binding.json
```

The same command supports the inverter-climate SetupHelper `.tar.gz`. An optional
`--verify-root /path/to/already-unpacked-package-root` compares a local distribution
without installing it. This is a payload comparison, not a running-process,
dependency, firmware ABI or thermostat qualification.

Stable releases can promote the exact RC bytes. In that case the release
manifest correctly retains its original RC `tag` and `source_sha`. The binding
records both the requested stable `release_tag` and original `build_tag`; it
does not rewrite the build's history or infer stability from the version file.

For the Cerbo runner, place the complete generated object in the reviewed schema
v2 inventory's `release_artifact`. Set `native_client_sha256` to its matching
`inverter_control/dbus_native.py` entry and retain the exact installed version
string in `controller_version`. Do not trim the file list to make a changed
installation pass. Keep local configuration separate from distributed payload
files and retain its reviewed identity privately. Extra operator files are not
included in the artifact claim; Python dependencies and the active process's
loaded modules need their own deployment record.

The example inventory stays disabled. Generating a binding does not authorize
execution, change a release channel, install software or enable a lab device.

## Cerbo execution and evidence

Use a dedicated attended lab and the existing [runner procedure](README.md).
Provision its explicit device identity, known host key, isolated runner and
reviewed `hardware-lab` environment before an executable dispatch. Record the
installed package, supervisor/process start after installation, Python and
dependency versions, Venus firmware, target/BMS identities and private
configuration identity. On-disk hashing alone cannot prove that an older
Python process has reloaded those bytes.

The runner checks the complete distributed payload before device-client imports
and after collection/cleanup. Its preflight event contains the full binding;
the offline evaluator requires exact equality with the reviewed inventory.
Keep `plan.json`, `events.jsonl`, `result.json`, `sha256.json`, immutable release
metadata and the operator deployment record together. A changed file, missing
evidence, failed cleanup or failed gate must remain a failure.

The current meter-loss scenario observes accepted-zero diagnostics and recovery.
It does not independently measure the physical power response or prove every
BMS write semantic. Add the target's independent readback/measurement record
before claiming those properties. Neither the disabled example nor synthetic
regression fixtures are device evidence.

## Thermostat acceptance is separate

Prepare the exact inverter-climate artifact binding and a dedicated test target.
Preserve its deployment, dependency and firmware identity, reviewed configuration
and single active command owner. Start with observation-only mode. In an attended
test, separately authorize manual commands and auto-preheat; retain bounded
command/readback evidence, stale telemetry behavior, loss and recovery of the
HA route, restart/journal behavior, and restoration of the initial target state.
Record uncertain outcomes without retrying a physical command merely to obtain
a passing result. Keep the previous known-good package and configuration for
an explicit rollback, then verify observation and readback after rollback.

There is no automated thermostat fault injector in this repository. A Cerbo
pass, wheel installation or SetupHelper validation cannot substitute for this
test. Publish a sanitized dated result only after it has actually been completed;
retain credentials, addresses and raw household data privately.
