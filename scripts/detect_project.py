#!/usr/bin/env python3
"""Detect common project characteristics without modifying the target repository."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SKIP_DIRS = {".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "vendor", ".venv", "venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", "target", "coverage", ".next", ".gradle"}
LANGUAGE_EXTENSIONS = {".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".fs": "F#", ".c": "C", ".h": "C/C++", ".cc": "C++", ".cpp": "C++", ".swift": "Swift", ".scala": "Scala", ".sh": "Shell", ".ps1": "PowerShell", ".dart": "Dart", ".ex": "Elixir", ".exs": "Elixir"}
MANIFESTS = {"package.json": "node", "pyproject.toml": "python", "requirements.txt": "python", "setup.py": "python", "setup.cfg": "python", "Pipfile": "python", "pom.xml": "java-maven", "build.gradle": "java-gradle", "build.gradle.kts": "java-gradle", "Cargo.toml": "rust", "go.mod": "go", "Gemfile": "ruby", "composer.json": "php", "mix.exs": "elixir"}
LOCKFILE_MANAGERS = {"pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "bun.lock": "bun", "bun.lockb": "bun", "uv.lock": "uv", "poetry.lock": "poetry", "Pipfile.lock": "pipenv", "pdm.lock": "pdm", "requirements.txt": "pip", "gradlew": "gradle-wrapper", "mvnw": "maven-wrapper"}
NODE_LOCKFILES = {name: LOCKFILE_MANAGERS[name] for name in ("pnpm-lock.yaml", "yarn.lock", "package-lock.json", "npm-shrinkwrap.json", "bun.lock", "bun.lockb")}
WORKSPACE_FILES = {"pnpm-workspace.yaml", "lerna.json", "nx.json", "turbo.json", "rush.json", "workspace.json", "settings.gradle", "settings.gradle.kts"}


def issue(path: str, kind: str, message: str) -> dict[str, str]:
    return {"path": path, "type": kind, "message": message}


def walk_files(root: Path, warnings: list[dict[str, str]], max_depth: int = 6) -> Iterable[Path]:
    def on_error(error: OSError) -> None:
        warnings.append(issue(str(Path(error.filename or root)), "directory_read_error", str(error)))

    for current, dirs, files in os.walk(root, onerror=on_error):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            warnings.append(issue(str(current_path), "path_resolution_error", "path is outside scan root"))
            continue
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".tox"))
        if depth >= max_depth:
            dirs[:] = []
        for name in sorted(files):
            yield current_path / name


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_package_json(path: Path, root: Path, warnings: list[dict[str, str]]) -> dict[str, Any] | None:
    path_text = relative(path, root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        warnings.append(issue(path_text, "manifest_read_error", str(exc)))
        return None
    except json.JSONDecodeError as exc:
        warnings.append(issue(path_text, "json_parse_error", f"{exc.msg} at line {exc.lineno}, column {exc.colno}"))
        return None
    if not isinstance(data, dict):
        warnings.append(issue(path_text, "manifest_format_error", "package.json root must be a JSON object"))
        return None
    return data


def adjacent_lockfile(manifest: Path, root: Path, warnings: list[dict[str, str]]) -> tuple[str | None, str | None]:
    found = [(name, manager) for name, manager in NODE_LOCKFILES.items() if (manifest.parent / name).is_file()]
    if len(found) > 1:
        warnings.append(issue(relative(manifest, root), "multiple_lockfiles", "multiple Node lockfiles exist beside this manifest"))
    if not found:
        return None, None
    name, manager = found[0]
    return relative(manifest.parent / name, root), manager


def node_package(path: Path, root: Path, warnings: list[dict[str, str]]) -> tuple[dict[str, Any], bool]:
    path_text = relative(path, root)
    data = read_package_json(path, root, warnings)
    lockfile, lock_manager = adjacent_lockfile(path, root, warnings)
    raw_scripts = data.get("scripts", {}) if data else {}
    if not isinstance(raw_scripts, dict):
        warnings.append(issue(path_text, "manifest_format_error", "scripts must be a JSON object"))
        raw_scripts = {}
    scripts = {key: value for key, value in raw_scripts.items() if isinstance(key, str) and isinstance(value, str)}
    if len(scripts) != len(raw_scripts):
        warnings.append(issue(path_text, "manifest_format_error", "non-string script entries were omitted"))
    declared = data.get("packageManager") if data else None
    declared_manager = declared.split("@", 1)[0] if isinstance(declared, str) and declared else None
    if declared is not None and not declared_manager:
        warnings.append(issue(path_text, "manifest_format_error", "packageManager must be a non-empty string"))
    if declared_manager and lock_manager and declared_manager != lock_manager:
        warnings.append(issue(path_text, "package_manager_conflict", "packageManager does not match the adjacent lockfile"))
    package = {
        "manifest": path_text,
        "package_name": data.get("name") if data and isinstance(data.get("name"), str) else None,
        "scripts": dict(sorted(scripts.items())),
        "has_build_script": "build" in scripts,
        "has_test_script": "test" in scripts,
        "has_lint_script": "lint" in scripts,
        "has_typecheck_script": any(name in scripts for name in ("typecheck", "type-check", "check-types")),
        "package_manager": declared_manager or lock_manager,
        "lockfile": lockfile,
        "manifest_valid": data is not None,
    }
    return package, bool(data and data.get("workspaces"))


def detect(root: Path) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    files = list(walk_files(root, warnings))
    names = Counter(path.name for path in files)
    language_counts = Counter(LANGUAGE_EXTENSIONS[path.suffix.lower()] for path in files if path.suffix.lower() in LANGUAGE_EXTENSIONS)
    manifests = [{"path": relative(path, root), "ecosystem": MANIFESTS[path.name]} for path in files if path.name in MANIFESTS]
    packages = []
    package_workspaces = []
    for path in (item for item in files if item.name == "package.json"):
        package, has_workspaces = node_package(path, root, warnings)
        packages.append(package)
        if has_workspaces:
            package_workspaces.append(f"{relative(path, root)}:workspaces")
    packages.sort(key=lambda package: package["manifest"])
    workspace_signals = sorted({relative(path, root) for path in files if path.name in WORKSPACE_FILES} | set(package_workspaces))
    monorepo_signals = []
    if len(packages) > 1:
        monorepo_signals.append("multiple_nested_manifests")
    if workspace_signals:
        monorepo_signals.append("workspace_configuration")
    ecosystems = sorted({item["ecosystem"] for item in manifests})
    managers = {package["package_manager"] for package in packages if package["package_manager"]}
    managers.update(manager for name, manager in LOCKFILE_MANAGERS.items() if names[name])
    return {
        "schema_version": 2, "root": str(root),
        "languages": [{"name": name, "file_count": count} for name, count in language_counts.most_common()],
        "ecosystems": ecosystems,
        "project_types": {"node": "node" in ecosystems, "python": "python" in ecosystems, "java": any(value.startswith("java-") for value in ecosystems)},
        "package_managers": sorted(managers), "manifests": manifests, "packages": packages,
        "repository_structure": {"multiple_packages": len(packages) > 1, "workspace_detected": bool(workspace_signals), "workspace_signals": workspace_signals, "monorepo_signals": monorepo_signals},
        "scan": {"max_depth": 6, "files_considered": len(files), "skipped_directories": sorted(SKIP_DIRS)},
        "errors": [], "warnings": sorted(warnings, key=lambda item: (item["path"], item["type"], item["message"])),
    }


def failure(root: Path, kind: str, message: str) -> dict[str, Any]:
    return {"schema_version": 2, "root": str(root), "errors": [issue(str(root), kind, message)], "warnings": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="repository path (default: current directory)")
    args = parser.parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(json.dumps(failure(root, "invalid_path", "path is not a directory"), indent=2))
        return 2
    try:
        result = detect(root)
    except OSError as exc:
        print(json.dumps(failure(root, "scan_error", str(exc)), indent=2))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
