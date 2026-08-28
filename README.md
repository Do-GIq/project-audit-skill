# project-audit

`project-audit` is a reusable Agent Skill for reviewing an arbitrary software repository's engineering quality and its readiness for submission or release. It combines deterministic, read-only Python checks with an Agent's contextual judgment.

## Why use it?

Release and submission reviews often miss basics: incomplete documentation, absent CI, stale temporary files, unclear environment setup, uncommitted work, or build and test commands that were never verified. This Skill provides a consistent evidence-gathering workflow without assuming a particular framework or business domain.

## Structure

```text
project-audit/
├── SKILL.md                       # Agent instructions, workflow, safety boundaries, and status model
├── README.md                      # Installation and usage guide
├── scripts/
│   ├── detect_project.py          # Project, ecosystem, package-manager, and workspace detection
│   ├── inspect_repo.py            # Deterministic repository-quality signals
│   └── check_git.py               # Read-only Git state inspection
└── references/
    └── audit-checklist.md         # Severity and assessment rules
```

## Installation

Copy or clone this directory into a skill discovery directory, keeping the directory name `project-audit`. For Codex, a typical personal installation is:

```text
~/.codex/skills/project-audit/
```

The installed directory must contain `SKILL.md` at its root. No Python dependencies are required beyond Python 3; the scripts use only the standard library.

## Invocation

Explicitly invoke the Skill in a request:

```text
Use $project-audit to assess this repository for release readiness.
```

For automatic discovery, install it in the Agent's configured skills directory and keep its `SKILL.md` frontmatter intact. Requests containing intents such as “project audit,” “repository review,” “release readiness,” “submission readiness,” or checks of README, CI, build, tests, lint, typecheck, and Git hygiene should match the description. Discovery behavior depends on the host Agent's skill-loading configuration.

## Current capabilities

- Detects common programming languages from bounded repository evidence.
- Recognizes Node, Python, Java/Maven, and Java/Gradle projects.
- Detects common manifests, package-local lockfiles and package managers, workspace configurations, and neutral multi-package/monorepo signals.
- Checks for README, `.gitignore`, environment examples, CI, test, lint, typecheck, and build signals.
- Reports package-level Node scripts and capabilities without hiding differences between packages.
- Flags common temporary artifacts and classifies potentially sensitive filenames as tracked, ignored, untracked, or unknown without reading their contents.
- Reports branch, working-tree state, changed paths, recent commit metadata, and remotes using read-only Git commands.
- Produces one overall assessment: `READY`, `READY WITH MINOR FIXES`, or `NOT READY`.

## Current limitations

- Detection is heuristic and cannot understand every ecosystem or repository convention.
- Presence of a file or script does not prove that a build, test, lint, typecheck, or CI workflow succeeds.
- The scripts do not install dependencies, execute builds or tests, validate remote CI status, inspect hosted pull requests, or access the network.
- Possible sensitive-file findings are filename-based; this version does not scan file contents for secrets.
- Large or unusual repositories may contain relevant configuration outside the bounded scan depth or ignored directories.
- The Skill does not fix issues, deploy software, publish releases, or perform destructive Git or database operations.
