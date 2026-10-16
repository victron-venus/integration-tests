# Architecture, assurance scope and roadmap

## Maintained source and trust boundaries

The Python suite creates isolated Docker Compose projects, synthetic battery/PV
publishers and a test runner. It builds the Python and Go dashboard revisions
pinned in `scripts/run-integration.py`, then verifies broker-to-dashboard state
and WebSocket behavior. The dashboards are external projects, not owned
implementations in this repository. The mock-only stack does not run the physical
inverter control loop. `tests`, `contracts` and `hardware` contain the behavioral,
configuration and safety tests. `scripts` also includes source-release,
workflow-generation and validation helpers.

The optional hardware runner is a separate operator workflow with allowlisted
targets and artifact/source identity checks. It uses OpenSSH with strict host-key
checking and inspects effective SSH settings before a connection. OpenSSH 9.1+
is required; RSA host keys must be at least 2048 bits, stronger operator settings
are retained, and connection multiplexing cannot reuse a weaker connection.
See [the hardware interface](../hardware/README.md) and
[acceptance contract](../hardware/RELEASE_ACCEPTANCE.md). Never turn a green mock
run into a statement about a physical device.

## Cryptography and supported configuration

Application mock traffic is local plaintext and does not offer encryption or
password storage. This project has no end-user password-verifier database or
custom cryptographic primitive. SHA-256 binds source/archive content and release
metadata. Git object identifiers are not newly designed security primitives.
Source-release helpers use GitHub CLI's maintained Go TLS implementation; use the
[verified strict release transport profile](release-tls-profile.md) for a
complete release-tool configuration. That profile preserves certificate and
hostname validation, TLS 1.2+, forward-secret key exchange and minimum
certificate key lengths. Operator SSH keys and trust stores require the checks
documented for the actual interface. Library and operating-system CSPRNGs supply
cryptographic randomness; test-data pseudorandom generators are not key sources.

No hosted check establishes that a deployment used the documented profile.
Ordinary compatibility settings, arbitrary proxies, custom trust stores or
external applications need their own assessment.

## Verification and reporting

`bash scripts/ci.sh syntax` parses owned source/configuration and validates
workflow semantics. `python3 -m pytest hardware/ contracts/ -q` exercises offline
safety contracts; `bash scripts/ci.sh python` and `bash scripts/ci.sh go` build
and run the isolated real-dashboard integrations. The required CI aggregate
requires both dashboard variants and safety contracts. Reports include JUnit,
HTML and container logs. The RC-only fuzz targets mutate the real compressed
archive parser and release identity validator without SSH or devices.

CodeQL and dependency analysis provide independent static/security checks.
Inspect actual findings and run logs, including skipped work. The source archive
is versioned and its inventory verified, but a source archive alone does not
prove bit-identical external container rebuilds. Fixed seed replay is separate
from an actual instrumented mutation campaign; see [fuzzing](fuzzing.md).

## Roadmap: October 2026 through October 2027

Over the next twelve months, maintain the existing release/integration contracts,
add measured coverage of owned production code and improve tests at malformed
input and unavailable-dependency boundaries. Review transport configuration and
operator guidance with every supported toolchain update. Establish and exercise
an authorized second-person repository, CI and release recovery arrangement.
Expand dashboard and release-acceptance scenarios without making real hardware a prerequisite for ordinary contribution tests.

The project will not certify physical safety from mocks, promise unattended
production installation, or replace the security review of external services.
New features remain proposals until implemented and verified. Universal
accessibility/internationalization, exhaustive input validation, complete
coverage and a formal security assurance case are not currently claimed.
[GOVERNANCE](../GOVERNANCE.md) records the confirmed absence of backup
maintainership and recovery within one week; those Silver requirements remain
unmet. [The official assessment](https://www.bestpractices.dev/en/projects/15554)
is the source of truth for criterion status and the live README badge.
