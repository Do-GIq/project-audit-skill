# project-audit

`project-audit` is a reusable Agent Skill for reviewing an arbitrary software repository's engineering quality and its readiness for submission or release. It combines deterministic, read-only Python checks with an Agent's contextual judgment.

When a compatible read-only GitHub MCP server is available, the Skill can optionally supplement local evidence with remote repository metadata, open pull requests, and recent GitHub Actions runs. The local audit remains complete and usable without MCP.

## Why use it?

Release and submission reviews often miss basics: incomplete documentation, absent CI, stale temporary files, unclear environment setup, uncommitted work, or build and test commands that were never verified. This Skill provides a consistent evidence-gathering workflow without assuming a particular framework or business domain.

## Structure

```text
project-audit/
├── install.ps1                    # Windows Skill and optional GitHub MCP installer
├── SKILL.md                       # Agent instructions, workflow, safety boundaries, and status model
├── README.md                      # Installation and usage guide
├── scripts/
│   ├── detect_project.py          # Project, ecosystem, package-manager, and workspace detection
│   ├── inspect_repo.py            # Deterministic repository-quality signals
│   └── check_git.py               # Read-only Git state inspection
├── references/
│   └── audit-checklist.md         # Severity and assessment rules
└── mcp-server/                    # Optional read-only GitHub MCP Server
```

## Quick Install

Windows PowerShell or PowerShell 7:

```powershell
git clone <project-audit-skill-repository-url> project-audit-skill
cd project-audit-skill
.\install.ps1
```

The installer places the Skill in `$HOME\.agents\skills\project-audit` and optionally installs the GitHub MCP integration in `$HOME\.codex\mcp\project-audit-github`.

- Local project auditing does not require a GitHub token.
- The GitHub MCP integration is optional and requires Python 3.10 or newer.
- For GitHub access, prefer a fine-grained personal access token with only Metadata read, Pull requests read, and Actions read permissions.
- Restart Codex Desktop after installing or updating the MCP integration.

## Manual Installation

Copy `SKILL.md`, `scripts/`, and `references/` into the following directory:

```text
~/.agents/skills/project-audit/
```

The installed directory must contain `SKILL.md` at its root. The local audit scripts use only the Python standard library.

To install the optional GitHub MCP manually, copy `mcp-server/server.py` and `mcp-server/pyproject.toml` into a separate user directory, create a Python 3.10+ virtual environment, run `python -m pip install -e .` with that environment, and configure the stdio server in `$HOME\.codex\config.toml`. Set `GITHUB_TOKEN` in `$HOME\.codex\.env`; never place the token in the repository or `config.toml`.

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
- Optionally uses `get_repository_info`, `get_open_pull_requests`, and `get_ci_status` for remote GitHub evidence during release, submission, PR, CI, or remote-repository reviews.
- Separates final results into Local Evidence, Remote Evidence, and Agent Assessment.
- Produces one overall assessment: `READY`, `READY WITH MINOR FIXES`, or `NOT READY`.

## Current limitations

- Detection is heuristic and cannot understand every ecosystem or repository convention.
- Presence of a file or script does not prove that a build, test, lint, typecheck, or CI workflow succeeds.
- The local scripts do not install dependencies, execute builds or tests, validate remote CI status, inspect hosted pull requests, or access the network. Remote GitHub checks require a separately configured compatible MCP server.
- If the GitHub MCP server, credentials, network, repository identity, or required tools are unavailable, remote checks are reported as not performed and the local audit continues.
- Possible sensitive-file findings are filename-based; this version does not scan file contents for secrets.
- Large or unusual repositories may contain relevant configuration outside the bounded scan depth or ignored directories.
- The Skill does not fix issues, deploy software, publish releases, or perform destructive Git or database operations.
