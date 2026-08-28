---
name: project-audit
description: Audit an arbitrary software repository for project audit, release readiness, repository review, or submission readiness, including README, CI, build, test, lint, typecheck, environment configuration, and Git hygiene checks. Use when the user wants an evidence-based readiness assessment without changing the repository.
---

# Project Audit

Assess a software repository's engineering quality and readiness to submit or release. Operate read-only by default: gather evidence, interpret it in the repository's context, and report findings. Do not fix findings unless the user makes a separate, explicit request.

## Workflow

1. Confirm the repository root and the requested scope. Treat the current repository as the root when the user does not specify another path.
2. Read [references/audit-checklist.md](references/audit-checklist.md) before assigning severity or final status.
3. Run `python scripts/detect_project.py <repo>` to identify languages, ecosystems, package managers, manifests, and monorepo/workspace signals. Run it for every full audit; skip it only when the user requests a narrowly scoped check unrelated to project detection.
4. Run `python scripts/inspect_repo.py <repo>` for deterministic repository checks. Run it for every full audit and for relevant README, CI, test, build, lint, typecheck, environment, or hygiene reviews.
5. Run `python scripts/check_git.py <repo>` for Git state. Run it for release readiness, submission readiness, Git hygiene, or a full audit. If Git is unavailable or the target is not a Git repository, report that result; do not treat tool failure as proof of a dirty tree.
6. Inspect the relevant manifests, configuration, documentation, and source layout. Use script output as evidence, not as the final judgment. Resolve ambiguous signals in context; for example, a library may not need an environment example and generated artifacts may be intentionally tracked.
7. When safe and in scope, run only project-defined, non-destructive verification commands that are already available locally, such as tests, lint, typecheck, or build. Do not install dependencies, access the network, or execute application/database lifecycle commands without explicit authorization. If commands are not run, say so.
8. Optionally perform the Remote GitHub Audit described below when its trigger and availability conditions are met. Remote evidence supplements local evidence; it never replaces the local workflow.
9. Classify findings as Critical, Warning, or Optional using the checklist. Cite paths and concise evidence. Distinguish confirmed failures from missing evidence and checks not run.
10. Assign exactly one overall status:
   - `READY`: no Critical or Warning findings; required verification succeeded or there is adequate evidence for the requested scope.
   - `READY WITH MINOR FIXES`: no Critical findings, but one or more bounded Warning findings remain.
   - `NOT READY`: one or more Critical findings exist, or required readiness cannot be established because essential build/test/release evidence is missing or failed.
11. Report the status first, then separate the evidence and judgment into `Local Evidence`, `Remote Evidence`, and `Agent Assessment`. Include scope, detected project shape, checks performed, findings by severity, checks not run, and prioritized next actions. Do not imply that an unexecuted check passed.

## Optional Remote GitHub Audit

Use remote GitHub evidence when the user requests release readiness, submission readiness, a remote repository check, PR status, or CI status, and an available MCP server exposes all applicable read-only tools:

- `get_repository_info` for remote repository metadata.
- `get_open_pull_requests` for open pull request state.
- `get_ci_status` for recent GitHub Actions workflow runs.

Determine the GitHub owner and repository from reliable user input or configured repository evidence. Do not guess when the identity is ambiguous.

Keep responsibilities distinct:

- Local scripts establish project structure, Git working-tree state, README and configuration presence, and local build/test/lint/typecheck evidence.
- GitHub MCP tools establish remote repository metadata, open pull requests, and recent GitHub Actions runs.
- The Agent reconciles local and remote facts and makes the readiness assessment.

Treat the MCP integration as an optional enhancement. If the MCP server, a required tool, credentials, network access, or repository identity is unavailable, continue the local audit and state under `Remote Evidence` that remote checks were not performed, including the reason when known. MCP unavailability alone must not make the project audit fail or change a local result to `NOT READY`.

Use only the three read-only tools listed above. Never use MCP to create, edit, close, dispatch, merge, push, publish, or otherwise mutate a pull request, issue, workflow, repository, release, or other GitHub resource.

## Script contract

All bundled scripts are Python 3, standard-library-only, read-only, offline helpers that emit JSON to stdout. Pass the repository path explicitly when it is not the current directory. Interpret package capabilities per manifest, distinguish configuration presence from executable commands, and use sensitive-file Git status instead of assuming a discovered file is committed. A nonzero exit, an `errors` entry, or a `warnings` entry is audit evidence to interpret, not permission to mutate the target.

## Prohibited actions

- Do not edit, generate, delete, rename, or format repository files during an audit.
- Do not install or update dependencies, lockfiles, toolchains, hooks, or global packages.
- Do not deploy, publish, upload, release, or contact external services except for the optional read-only GitHub MCP checks defined above.
- Do not run database migrations, seeds, resets, destructive application commands, or commands requiring secrets.
- Do not execute Git `push`, `pull`, `merge`, `reset`, `rebase`, `checkout`, branch deletion, commit, clean, stash, tag creation, or history rewriting.
- Do not expose secret contents. Report only a path, category, and safe evidence when a possible secret or sensitive file is found.
- Do not claim readiness solely from filenames or script heuristics; the Agent owns semantic judgment.
