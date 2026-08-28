#!/usr/bin/env python3
"""Read-only GitHub MCP server for repository audit evidence."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server import MCPServer


GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
REQUEST_TIMEOUT_SECONDS = 20
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

mcp = MCPServer(
    "project-audit-github",
    version="0.1.0",
    instructions="Read-only GitHub repository metadata for project audits.",
)


def _error(code: str, message: str, status: int | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {"code": code, "status": status, "message": message},
    }


def _success(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def _validate_repository(owner: str, repo: str) -> dict[str, Any] | None:
    if not owner or not repo:
        return _error("invalid_input", "owner and repo must be non-empty")
    if not NAME_PATTERN.fullmatch(owner) or not NAME_PATTERN.fullmatch(repo):
        return _error("invalid_input", "owner and repo contain unsupported characters")
    return None


def _github_get(path: str, query: dict[str, str] | None = None) -> tuple[Any | None, dict[str, Any] | None]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None, _error("missing_token", "GITHUB_TOKEN is not configured")

    url = f"{GITHUB_API_BASE}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "project-audit-github-mcp/0.1.0",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response), None
    except urllib.error.HTTPError as exc:
        message = "GitHub API request failed"
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            if isinstance(payload, dict) and isinstance(payload.get("message"), str):
                message = payload["message"]
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
        return None, _error("github_api_error", message, exc.code)
    except urllib.error.URLError as exc:
        return None, _error("network_error", f"GitHub API is unreachable: {exc.reason}")
    except TimeoutError:
        return None, _error("timeout", "GitHub API request timed out")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, _error("response_error", f"Could not read the GitHub API response: {exc}")


def _repository_path(owner: str, repo: str) -> str:
    return f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}"


@mcp.tool()
def get_repository_info(owner: str, repo: str) -> dict[str, Any]:
    """Return read-only metadata for a GitHub repository."""
    invalid = _validate_repository(owner, repo)
    if invalid:
        return invalid
    payload, error = _github_get(_repository_path(owner, repo))
    if error:
        return error
    if not isinstance(payload, dict):
        return _error("unexpected_response", "GitHub returned an unexpected repository response")
    return _success({
        "full_name": payload.get("full_name"),
        "default_branch": payload.get("default_branch"),
        "visibility": payload.get("visibility"),
        "private": payload.get("private"),
        "archived": payload.get("archived"),
        "open_issues_count": payload.get("open_issues_count"),
        "updated_at": payload.get("updated_at"),
    })


@mcp.tool()
def get_open_pull_requests(owner: str, repo: str) -> dict[str, Any]:
    """Return open pull requests without changing them."""
    invalid = _validate_repository(owner, repo)
    if invalid:
        return invalid
    payload, error = _github_get(
        f"{_repository_path(owner, repo)}/pulls",
        {"state": "open", "per_page": "100", "sort": "updated", "direction": "desc"},
    )
    if error:
        return error
    if not isinstance(payload, list):
        return _error("unexpected_response", "GitHub returned an unexpected pull request response")
    pull_requests = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        head = item.get("head") if isinstance(item.get("head"), dict) else {}
        base = item.get("base") if isinstance(item.get("base"), dict) else {}
        pull_requests.append({
            "number": item.get("number"),
            "title": item.get("title"),
            "state": item.get("state"),
            "draft": item.get("draft"),
            "head_branch": head.get("ref"),
            "base_branch": base.get("ref"),
            "updated_at": item.get("updated_at"),
        })
    return _success(pull_requests)


@mcp.tool()
def get_ci_status(owner: str, repo: str) -> dict[str, Any]:
    """Return recent GitHub Actions workflow runs without dispatching workflows."""
    invalid = _validate_repository(owner, repo)
    if invalid:
        return invalid
    payload, error = _github_get(
        f"{_repository_path(owner, repo)}/actions/runs",
        {"per_page": "20"},
    )
    if error:
        return error
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        return _error("unexpected_response", "GitHub returned an unexpected workflow runs response")
    runs = []
    for item in payload["workflow_runs"]:
        if not isinstance(item, dict):
            continue
        runs.append({
            "workflow_name": item.get("name"),
            "branch": item.get("head_branch"),
            "event": item.get("event"),
            "status": item.get("status"),
            "conclusion": item.get("conclusion"),
            "created_at": item.get("created_at"),
            "html_url": item.get("html_url"),
        })
    return _success(runs)


if __name__ == "__main__":
    mcp.run()
