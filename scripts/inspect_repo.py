#!/usr/bin/env python3
"""Perform deterministic, read-only repository checks and emit JSON."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv", "__pycache__", "dist", "build", "target", ".gradle"}
README_NAMES = {"readme", "readme.md", "readme.rst", "readme.txt", "readme.adoc"}
ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template", ".env.defaults", "example.env", "sample.env"}
CI_PATHS = {".gitlab-ci.yml", ".gitlab-ci.yaml", "Jenkinsfile", "azure-pipelines.yml", "azure-pipelines.yaml", "bitbucket-pipelines.yml", ".circleci/config.yml", ".circleci/config.yaml", ".travis.yml", "appveyor.yml"}
TEST_DIRS = {"test", "tests", "spec", "specs", "__tests__", "integration-tests", "e2e"}
TEST_CONFIGS = {"pytest.ini", "tox.ini", "noxfile.py", "jest.config.js", "jest.config.ts", "vitest.config.js", "vitest.config.ts", "playwright.config.js", "playwright.config.ts", "karma.conf.js", "phpunit.xml", "phpunit.xml.dist"}
LINT_CONFIGS = {".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", ".ruff.toml", ".flake8", "pylintrc", ".pylintrc", "checkstyle.xml", "detekt.yml", ".golangci.yml", ".golangci.yaml", "clippy.toml"}
TYPESCRIPT_CONFIGS = {"tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "tsconfig.build.json"}
OTHER_TYPECHECK_CONFIGS = {"mypy.ini", ".mypy.ini", "pyrightconfig.json", "sorbet/config"}
BUILD_CONFIGS = {"pyproject.toml", "setup.py", "pom.xml", "build.gradle", "build.gradle.kts", "Makefile", "CMakeLists.txt", "Cargo.toml", "go.mod", "build.xml"}
TEMP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", "npm-debug.log", "yarn-debug.log", "yarn-error.log", ".coverage"}
TEMP_SUFFIXES = {".tmp", ".temp", ".swp", ".swo", ".bak", ".orig", ".rej", ".pyc", ".class"}
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", ".env.development", "id_rsa", "id_ed25519", "credentials.json", "service-account.json", "secrets.yml", "secrets.yaml"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore", ".jks"}
NODE_LOCKFILES = {"pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "bun.lock": "bun", "bun.lockb": "bun"}
TYPECHECK_SCRIPT_NAMES = {"typecheck", "type-check", "check-types"}
CI_TYPECHECK_PATTERN = re.compile(r"(?:^|[\s:\"'])((?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:typecheck|type-check|check-types)|(?:npx\s+)?tsc(?:\s|$)|mypy(?:\s|$)|pyright(?:\s|$))", re.IGNORECASE | re.MULTILINE)


def issue(path: str, kind: str, message: str) -> dict[str, str]:
    return {"path": path, "type": kind, "message": message}


def walk(root: Path, warnings: list[dict[str, str]], max_depth: int = 6) -> Iterable[Path]:
    def on_error(error: OSError) -> None:
        warnings.append(issue(str(Path(error.filename or root)), "directory_read_error", str(error)))

    for current, dirs, files in os.walk(root, onerror=on_error):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            warnings.append(issue(str(current_path), "path_resolution_error", "path is outside scan root"))
            continue
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        if depth >= max_depth:
            dirs[:] = []
        for name in sorted(files):
            yield current_path / name


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def matches(files: list[Path], root: Path, names: set[str]) -> list[str]:
    return sorted(rel(path, root) for path in files if path.name in names or rel(path, root) in names)


def read_package(path: Path, root: Path, warnings: list[dict[str, str]]) -> dict[str, Any] | None:
    path_text = rel(path, root)
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


def package_lockfile(path: Path, root: Path, warnings: list[dict[str, str]]) -> tuple[str | None, str | None]:
    found = [(name, manager) for name, manager in NODE_LOCKFILES.items() if (path.parent / name).is_file()]
    if len(found) > 1:
        warnings.append(issue(rel(path, root), "multiple_lockfiles", "multiple Node lockfiles exist beside this manifest"))
    if not found:
        return None, None
    name, manager = found[0]
    return rel(path.parent / name, root), manager


def node_packages(files: list[Path], root: Path, warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    packages = []
    for path in (item for item in files if item.name == "package.json"):
        data = read_package(path, root, warnings)
        lockfile, lock_manager = package_lockfile(path, root, warnings)
        raw_scripts = data.get("scripts", {}) if data else {}
        if not isinstance(raw_scripts, dict):
            warnings.append(issue(rel(path, root), "manifest_format_error", "scripts must be a JSON object"))
            raw_scripts = {}
        scripts = {key: value for key, value in raw_scripts.items() if isinstance(key, str) and isinstance(value, str)}
        if len(scripts) != len(raw_scripts):
            warnings.append(issue(rel(path, root), "manifest_format_error", "non-string script entries were omitted"))
        declared = data.get("packageManager") if data else None
        declared_manager = declared.split("@", 1)[0] if isinstance(declared, str) and declared else None
        if declared is not None and not declared_manager:
            warnings.append(issue(rel(path, root), "manifest_format_error", "packageManager must be a non-empty string"))
        if declared_manager and lock_manager and declared_manager != lock_manager:
            warnings.append(issue(rel(path, root), "package_manager_conflict", "packageManager does not match the adjacent lockfile"))
        packages.append({
            "manifest": rel(path, root),
            "package_name": data.get("name") if data and isinstance(data.get("name"), str) else None,
            "scripts": dict(sorted(scripts.items())),
            "package_manager": declared_manager or lock_manager,
            "lockfile": lockfile,
            "typescript_config_present": any(candidate.name.startswith("tsconfig") and candidate.suffix == ".json" and candidate.parent == path.parent for candidate in files),
            "capabilities": {"build": "build" in scripts, "test": "test" in scripts, "lint": "lint" in scripts, "typecheck_command": any(name in scripts for name in TYPECHECK_SCRIPT_NAMES)},
            "manifest_valid": data is not None,
        })
    return sorted(packages, key=lambda package: package["manifest"])


def read_text_signal(path: Path, root: Path, warnings: list[dict[str, str]], kind: str) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="strict")[:250_000]
    except (OSError, UnicodeError) as exc:
        warnings.append(issue(rel(path, root), kind, str(exc)))
        return ""


def ci_typecheck_paths(ci_paths: list[str], root: Path, warnings: list[dict[str, str]]) -> list[str]:
    return sorted(path_text for path_text in ci_paths if CI_TYPECHECK_PATTERN.search(read_text_signal(root / Path(path_text), root, warnings, "ci_read_error")))


def git_run(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError:
        return None


def sensitive_git_status(path_text: str, root: Path, warnings: list[dict[str, str]]) -> str:
    probe = git_run(root, "rev-parse", "--is-inside-work-tree")
    if probe is None or probe.returncode != 0 or probe.stdout.strip() != "true":
        return "unknown"
    tracked = git_run(root, "ls-files", "--error-unmatch", "--", path_text)
    if tracked is None:
        warnings.append(issue(path_text, "git_unavailable", "git executable became unavailable during status check"))
        return "unknown"
    if tracked.returncode == 0:
        return "tracked"
    ignored = git_run(root, "check-ignore", "-q", "--", path_text)
    if ignored is None:
        warnings.append(issue(path_text, "git_unavailable", "git executable became unavailable during status check"))
        return "unknown"
    if ignored.returncode == 0:
        return "ignored"
    if ignored.returncode == 1:
        return "untracked"
    warnings.append(issue(path_text, "git_status_error", ignored.stderr.strip() or "could not determine ignore status"))
    return "unknown"


def inspect(root: Path) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    files = list(walk(root, warnings))
    relative_files = {rel(path, root) for path in files}
    packages = node_packages(files, root, warnings)
    readmes = sorted(rel(path, root) for path in files if path.name.lower() in README_NAMES)
    ci = matches(files, root, CI_PATHS)
    ci.extend(path for path in relative_files if path.startswith(".github/workflows/") and Path(path).suffix.lower() in {".yml", ".yaml"})
    ci = sorted(set(ci))
    test_dirs = sorted({rel(path.parent, root) for path in files if path.parent.name.lower() in TEST_DIRS})
    test_configs = matches(files, root, TEST_CONFIGS)
    lint_configs = matches(files, root, LINT_CONFIGS)
    typescript_configs = sorted(rel(path, root) for path in files if path.name in TYPESCRIPT_CONFIGS or (path.name.startswith("tsconfig.") and path.suffix == ".json"))
    other_typecheck_configs = matches(files, root, OTHER_TYPECHECK_CONFIGS)
    build_configs = matches(files, root, BUILD_CONFIGS)
    for path in (item for item in files if item.name == "pyproject.toml"):
        text = read_text_signal(path, root, warnings, "config_read_error")
        path_text = rel(path, root)
        if any(marker in text for marker in ("[tool.pytest", "[tool.coverage")):
            test_configs.append(path_text)
        if any(marker in text for marker in ("[tool.ruff", "[tool.black", "[tool.pylint")):
            lint_configs.append(path_text)
        if "[tool.mypy" in text or "[tool.pyright" in text:
            other_typecheck_configs.append(path_text)
    package_manifests = {capability: [package["manifest"] for package in packages if package["capabilities"][capability]] for capability in ("build", "test", "lint", "typecheck_command")}
    ci_typechecks = ci_typecheck_paths(ci, root, warnings)
    temporary = sorted(rel(path, root) for path in files if path.name in TEMP_NAMES or path.suffix.lower() in TEMP_SUFFIXES)
    sensitive_paths = sorted(rel(path, root) for path in files if path.name.lower() in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_SUFFIXES)
    sensitive = [{"path": path, "git_status": sensitive_git_status(path, root, warnings)} for path in sensitive_paths]
    env_examples = matches(files, root, ENV_EXAMPLES)
    gitignores = sorted(path for path in relative_files if Path(path).name == ".gitignore")
    return {
        "schema_version": 2, "root": str(root), "packages": packages,
        "checks": {
            "readme": {"present": bool(readmes), "paths": readmes},
            "gitignore": {"present": bool(gitignores), "paths": gitignores},
            "environment_example": {"present": bool(env_examples), "paths": env_examples},
            "ci": {"present": bool(ci), "paths": ci},
            "tests": {"present": bool(test_dirs or test_configs or package_manifests["test"]), "directories": test_dirs, "configs": sorted(set(test_configs)), "package_script_manifests": package_manifests["test"]},
            "lint": {"present": bool(lint_configs or package_manifests["lint"]), "configs": sorted(set(lint_configs)), "package_script_manifests": package_manifests["lint"]},
            "typecheck": {"typescript_config_present": bool(typescript_configs), "typescript_configs": typescript_configs, "other_configs": sorted(set(other_typecheck_configs)), "typecheck_command_present": bool(package_manifests["typecheck_command"] or ci_typechecks), "package_script_manifests": package_manifests["typecheck_command"], "ci_command_present": bool(ci_typechecks), "ci_paths": ci_typechecks},
            "build": {"present": bool(build_configs or package_manifests["build"]), "configs": sorted(set(build_configs)), "package_script_manifests": package_manifests["build"]},
            "temporary_files": {"present": bool(temporary), "paths": temporary},
            "potentially_sensitive_files": {"present": bool(sensitive), "files": sensitive, "note": "Filename heuristic only; contents and secret values were not inspected."},
        },
        "summary": {"package_count": len(packages), "packages_with_build_script": package_manifests["build"], "packages_with_test_script": package_manifests["test"], "packages_with_lint_script": package_manifests["lint"], "packages_with_typecheck_script": package_manifests["typecheck_command"]},
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
        result = inspect(root)
    except OSError as exc:
        print(json.dumps(failure(root, "scan_error", str(exc)), indent=2))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
