# Documentation

A cross-service integration suite that provisions isolated Docker Compose
projects, with its assurance scope and release records.

## The suite

- [Architecture, assurance scope and roadmap](project-assurance.md) — what the suite creates and which services it exercises.

## Assurance

- [OpenSSF Best Practices evidence: integration-tests](openssf-evidence.md) — the index behind the assessment and what the official record says.

## Releases

- [Release version files](release-versioning.md) — `SOURCE_VERSION`, `pyproject.toml` and the local version file the policy owns.
- [Release helper TLS profile](release-tls-profile.md) — the qualified `gh` transport profile.
- [CI and release operations](release-workflow.md) — `.release-policy.json` and the required status.
- [CI orchestration](CI-ORCHESTRATION.md) — how the quality gate and release pipeline divide the events.
- [CI and release policy](CI_WORKFLOW.md) — the validation-only policy and its events.
- [Version plans and manifest synchronization](VERSIONING.md) — the versioning opt-in.
- [RC-only fuzz testing](fuzzing.md) — why fuzzing runs only on release candidates.
- [Fuzzing release candidates](rc-fuzzing.md) — the reusable bounded fuzz workflow.
- [Release read recovery and rerun validation](release-read-safety.md) — the two fixes carried from the shared toolkit.
- [Early final-build runner check](runner-preflight.md) — why the check runs before the final build.
