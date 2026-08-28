# project-audit GitHub MCP Server

A minimal, read-only MCP server that supplies remote GitHub repository evidence to an Agent using the `project-audit` Skill. It exposes repository metadata, open pull requests, and recent GitHub Actions runs over stdio.

## Requirements

- Python 3.10 or newer
- A GitHub token in `GITHUB_TOKEN`
- Network access to `https://api.github.com`

Use a fine-grained GitHub token with only the read permissions needed for repository metadata, pull requests, and Actions. The server reads the token from the process environment; it does not load `.env` automatically.

## Install

From this directory, create and activate a virtual environment, then install the server:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

For the optional MCP development CLI and Inspector support:

```powershell
python -m pip install -e ".[dev]"
```

## Configure

Set the token in the environment of the process that launches the server. Do not commit a real token.

```powershell
$env:GITHUB_TOKEN = "your-token"
```

`.env.example` documents the required variable, but `server.py` intentionally does not parse `.env` files or print the token.

## Run locally

The default transport is stdio:

```powershell
python server.py
```

With the optional MCP CLI installed, the equivalent SDK runner command is:

```powershell
mcp run server.py
```

When started directly, the process waits for an MCP host to communicate over stdin/stdout. It does not open an HTTP port.

## Tools

- `get_repository_info(owner, repo)` returns the repository name, default branch, visibility/private flags, archive state, open issue count, and update time.
- `get_open_pull_requests(owner, repo)` returns up to 100 open pull requests, most recently updated first.
- `get_ci_status(owner, repo)` returns the 20 most recent GitHub Actions workflow runs.

Every tool returns a stable envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

Failures return `ok: false`, `data: null`, and an error object containing `code`, `status`, and `message`. A failed GitHub request does not stop the MCP server.

## Read-only boundary

The implementation sends only GitHub REST `GET` requests. It cannot create, update, close, dispatch, merge, push, publish, or otherwise mutate GitHub resources.

## Current limitations

- Pull requests are limited to the first 100 open results; pagination is not implemented.
- CI status is limited to the 20 most recent GitHub Actions workflow runs.
- Only GitHub Actions is inspected; other CI providers are outside this version.
- The server does not aggregate required checks or calculate an overall release-readiness status.
- GitHub rate limits, token scopes, organization policies, and repository visibility can affect results.
- Retries and response caching are not implemented.
