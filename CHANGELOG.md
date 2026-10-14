# Changelog

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

