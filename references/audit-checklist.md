# Project audit checklist

Use this checklist to interpret repository evidence. Severity is contextual: confirm that a rule applies to the repository and requested readiness target before recording a finding. Absence of a conventional file is not automatically a defect when equivalent evidence exists elsewhere.

## Severity model

- **Critical**: Blocks safe build, verification, submission, or release; creates a material security/reproducibility risk; or leaves essential readiness unestablished.
- **Warning**: A real, bounded quality or maintainability gap that should be corrected soon but does not independently block the stated release or submission.
- **Optional**: A beneficial improvement, convention, or maturity enhancement with no current readiness impact.

Final status mapping:

- `READY`: no Critical or Warning findings and adequate evidence exists for the requested scope.
- `READY WITH MINOR FIXES`: no Critical findings; only bounded Warning findings remain.
- `NOT READY`: at least one Critical finding, or essential build/test/release evidence is missing or failed.

## Repository hygiene

**Critical**

- Confirmed credentials, private keys, production secrets, or other sensitive material are tracked or exposed.
- Required source, manifest, or lock data is missing such that the repository cannot be reproduced or evaluated.

**Warning**

- `.gitignore` or an equivalent ignore mechanism is absent where generated, local, or sensitive files are expected.
- Temporary, editor, log, cache, compiled, or generated artifacts appear unintentionally committed.
- Repository layout or ownership of generated artifacts is ambiguous enough to hinder review.

**Optional**

- Add repository-wide formatting/editor conventions or clearer generated-file policies.

## Build readiness

**Critical**

- The documented, required build fails under the stated supported environment.
- No build/package entry point can be identified for a deliverable that requires one.
- Required dependency metadata is internally inconsistent or essential local dependencies are unavailable.

**Warning**

- Build instructions, prerequisites, supported runtime versions, or artifact expectations are incomplete.
- Reproducibility is weakened by missing version constraints or an unexpectedly absent lockfile where the project convention requires one.

**Optional**

- Improve build caching, artifact metadata, or developer convenience commands.

## Tests

**Critical**

- Required tests fail, cannot start, or do not cover a release-critical path when that coverage is necessary for the stated readiness target.
- The repository claims passing tests but available evidence contradicts that claim.

**Warning**

- No automated tests or test command can be found for code whose behavior warrants verification.
- Test setup, fixtures, or local execution instructions are incomplete.
- Important behavior has weak coverage, flaky tests, or tests that are disabled without explanation.

**Optional**

- Expand non-critical coverage, performance tests, mutation tests, or coverage reporting.

## Lint and type checking

**Critical**

- A required release gate fails and indicates likely correctness, security, or compilation defects.

**Warning**

- Applicable lint or typecheck tooling is absent, undocumented, not runnable, or reports unresolved violations.
- Configuration exists but is not connected to developer or CI workflows.

**Optional**

- Tighten rules, broaden typed coverage, or improve formatting automation when current checks are adequate.

## Documentation

**Critical**

- Essential setup, operation, safety, migration, or release instructions are missing or materially incorrect, preventing safe evaluation or use.
- Licensing or required notices are absent when they are mandatory for the intended submission or distribution.

**Warning**

- No README or equivalent entry documentation exists.
- Setup, build, test, configuration, architecture, or usage guidance is incomplete for the intended audience.
- Documented commands or paths are stale.

**Optional**

- Add contribution guidance, architecture decisions, examples, troubleshooting, changelog, or richer API documentation.

## Environment configuration

**Critical**

- Real secrets are committed or required secrets are handled unsafely.
- The application requires environment values but their purpose and safe provisioning cannot be established.

**Warning**

- Environment-dependent software lacks a sanitized example/template or an equivalent variable reference.
- Required versus optional variables, defaults, validation, or runtime versions are unclear.

**Optional**

- Add schema validation, generated reference documentation, or more developer-friendly defaults.

Do not penalize repositories that do not use environment configuration for lacking an environment example.

## Continuous integration

**Critical**

- Mandatory CI gates fail or the release process depends on CI that is broken or unsafe.
- CI exposes secrets, runs untrusted code with unsafe privileges, or can publish without required controls.

**Warning**

- No CI exists for a repository whose submission or release process expects automated verification.
- CI omits applicable build, tests, lint/typecheck, or supported environments.
- Workflow configuration is present but stale, disabled, or inconsistent with documented commands.

**Optional**

- Improve caching, matrices, artifact retention, reporting, or non-blocking quality analysis.

## Git state

**Critical**

- Release/submission content is not committed, the intended revision cannot be identified, or unresolved conflicts exist.
- The checked revision is demonstrably not the revision intended for submission or release.

**Warning**

- The working tree is dirty during a final readiness review.
- The repository has no commits, is unexpectedly detached, or lacks a remote when a remote-backed submission/release is expected.
- Recent commit metadata or history does not provide adequate traceability for the stated process.

**Optional**

- Improve commit clarity, tags, branch naming, or release-history conventions.

## Evidence rules

- State whether each conclusion comes from file inspection, a bundled script, or an executed project command.
- Treat filename heuristics as leads. Use the reported Git status to distinguish tracked, ignored, untracked, and unknown sensitive-file candidates; presence alone does not mean a file was committed. Never label a file as a confirmed secret without safe evidence, and never print secret contents.
- Evaluate build, test, lint, and typecheck capabilities per package. A configuration file such as `tsconfig.json` is not evidence that an executable command exists.
- Record commands not run and why. “Not run” is distinct from “passed” and from “failed.”
- Adapt expectations to the repository type: applications, libraries, documentation-only repositories, infrastructure, prototypes, and monorepos have different legitimate requirements.
- Prefer a small set of actionable findings over speculative completeness. Include paths and the next verification step.
