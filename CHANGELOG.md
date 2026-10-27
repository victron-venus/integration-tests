# Changelog

## [0.1.6] - 2026-10-27

### Changed

- Refresh the synthetic device container base images and the locked WebSocket test client to 17.3.
- Preserve the synthetic fixtures and the existing native architecture qualification gates.

### Upgrade

Extract the new source suite into a separate directory and use its committed dependency locks and container definitions. Preserve local test configuration and keep the previous suite available for rollback. No application-data migration is required.

### Security

Run the suite against isolated synthetic services with test credentials. Updated images and the WebSocket client do not authorize production deployment or establish physical-device acceptance; retain the existing security and native architecture validation gates.

## [0.1.5] - 2026-10-24

### Changed

- Publish the updated source suite with the patched uv 0.13.4 bootstrap in the
  Python dashboard integration container and current release provenance checks.

### Security

- The included uv bootstrap no longer carries the distrusted
  emSign ECC Root CA - G3 (GHSA-hq85-5cpj-mr62). Archive hashes remain verified before installation.
  The suite continues to run isolated synthetic services; publishing it does not
  deploy applications or establish physical-device acceptance.

### Upgrade

- Extract the new source suite into a separate directory and use the committed
  dependency locks. Preserve local configuration and keep the previous version
  available for rollback. No application-data migration is required.

## [0.1.4] - 2026-10-18

### Changed

- Route Dependabot metadata approval through the trusted default branch while preserving the existing author and review policy.
- Refresh pinned shared CI workflows and their source-bound release validation.

### Upgrade

Use the documented upgrade procedure and preserve local configuration and data. No configuration migration is required. Keep the previous immutable release available for rollback.

### Security

This maintenance release preserves the existing security and release-validation requirements. Publication does not deploy the service or establish physical-device acceptance.

## [0.1.3] - 2026-10-17

- Keep the local package version in `uv.lock` synchronized through the release policy.
- Synchronize the uv lock with the already declared websockets 17.2 dependency and check project dependencies against the runner pins in CI.
- Include pytest-asyncio in the offline contract environment so the shared
  asyncio configuration is recognized without warnings.

- Document governance, private conduct reporting, the maintained architecture and
  assurance scope; link the official OpenSSF assessment from the README.
- Clarify the 60-day fix policy for publicly known medium-or-higher vulnerabilities.

### Upgrade

Extract the source suite into a separate directory and use its committed dependency locks. Preserve local configuration; production deployment and device acceptance remain separate.

### Security

The source and dependency-maintenance changes preserve the existing validation gates. No new application vulnerability fix or target-device acceptance is claimed.

## [0.1.2] - 2026-10-14

### Changed

- Require positive fuzz engine execution counts, instrumented production code and validated seed corpora before accepting RC evidence.
- Add regression tests for malformed reports, unsafe corpora and incomplete seed replay; retain the existing coverage requirements.
- Keep mutation campaigns restricted to public RCs and use deterministic seed checks in ordinary CI.

### Upgrade

Use the documented update procedure and preserve local configuration. No application configuration or data migration is introduced. Keep the previous accepted package available for rollback; the exact candidate still requires applicable device and integration acceptance.

### Security

The release gate fails closed on absent, invalid or incomplete fuzz evidence. No application vulnerability or new hardware acceptance is claimed by this validation update.

## [0.1.1]

### Added

- RC-only fuzzing of real pure input handlers, with documented synthetic seeds and bounded execution.
- Reviewed source archives with isolated acceptance, frozen versions, receipts and checksums.

### Upgrade

Extract the new source suite into a separate directory. Preserve local configuration
and device state. This package does not deploy or install itself on any device.

### Security

The source suite and test corpus contain no private captures or credentials.
Fuzz campaigns cannot contact devices; actual hardware acceptance is separate.

