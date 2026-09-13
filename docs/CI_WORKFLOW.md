# CI and release policy

This repository has a validation-only policy. The `Quality gate` workflow runs
on pull requests, merge queue entries, the default branch, and a staggered
nightly UTC schedule. Every configured validation workflow must finish
successfully; a skipped or failed workflow does not pass `CI gate`.

Install actionlint 1.7.12 (and Node.js when JavaScript sources are present).
Run the same local checks:

```sh
python3 -m pip install PyYAML==6.0.3
bash scripts/ci.sh
```

Request or inspect CI from a local checkout:

```sh
gh workflow run quality-gate.yml
gh run list --workflow quality-gate.yml
```

No beta, RC or stable application release is synthesized from configuration or
reference source. Disabled legacy publisher entry points only explain this
migration. Their exact previous contents remain in `docs/legacy-workflows/`.
Production deployment, where provided, requires manual dispatch from the default
branch and the `production` environment; validation never deploys resources.

Install Docker with Compose and Git. `bash scripts/ci.sh python` or `go` checks out the pinned dashboard revision and runs the existing MQTT/D-Bus mock suite. The default runs both. Containers use isolated project names/networks with no host ports. Reports are copied into `reports/` before the temporary stack is removed. These are current working-tree suite tests against pinned consumers.

## Coverage limits

- Validation-only policy: no synthetic beta/RC artifacts or tag-triggered stable releases.
- Docker matrix tests pinned Python/Go dashboards with mocks; no guarantee for every current consumer commit or real hardware.
