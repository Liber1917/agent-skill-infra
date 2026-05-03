#!/usr/bin/env python3
"""Issue-triggered test runner for agent-skill-infra.

Reads ISSUE_BODY and ISSUE_NUMBER from environment, parses the repo URL,
clones the target, detects project type, runs tests, and posts a report
comment back to the issue.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_URL_RE = re.compile(r"https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?(?:\s|$)")

TIMEOUT_INSTALL = 180  # seconds for dependency install
TIMEOUT_TEST = 300  # seconds for test execution


# ---------------------------------------------------------------------------
# GitHub API helper (stdlib only — no httpx dependency)
# ---------------------------------------------------------------------------


def _gh_api(method: str, path: str, body: dict[str, Any] | None = None) -> dict:
    token = os.environ.get("GH_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "Liber1917/agent-skill-infra")
    url = f"https://api.github.com/repos/{repo}/{path}"

    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")

    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Issue parsing
# ---------------------------------------------------------------------------


def parse_issue_body(body: str) -> dict[str, str]:
    """Extract fields from a GitHub issue form body."""
    result: dict[str, str] = {}
    current_key: str | None = None

    for line in body.splitlines():
        stripped = line.strip()
        # GitHub issue forms use "### Field Label" as headers
        if stripped.startswith("### "):
            label = stripped[4:].strip()
            # Map labels to field IDs
            mapping = {
                "Repository URL": "repo_url",
                "Branch (optional)": "branch",
                "Custom test command (optional)": "test_command",
                "Additional notes (optional)": "notes",
            }
            current_key = mapping.get(label)
        elif current_key and stripped and not stripped.startswith("_"):
            # Skip the form description line (starts with _)
            val = stripped.strip()
            if val and not val.startswith("Submit a"):
                result[current_key] = val

    return result


def extract_repo_url(body: str) -> tuple[str, str] | None:
    """Extract (owner, repo_name) from issue body. Returns None if not found."""
    match = REPO_URL_RE.search(body)
    if match:
        return match.group(1), match.group(2).rstrip("/")
    return None


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------


def detect_project_type(repo_dir: Path) -> str:
    """Detect the project type by scanning for known files."""
    files = {f.name for f in repo_dir.iterdir() if f.is_file()}
    dirs = {d.name for d in repo_dir.iterdir() if d.is_dir()}

    # Single SKILL.md at root — pure skill repo (most common case)
    if "SKILL.md" in files:
        return "skill"

    # Bun project
    if "bun.lock" in files or "bunfig.toml" in files:
        return "bun"

    # Python project
    if "pyproject.toml" in files:
        return "python"

    # Node/npm project
    if "package.json" in files:
        return "npm"

    # Config-driven Agent Skill collection (ecc-style)
    config_dirs = {"agents", "skills", "commands", "rules", "hooks"}
    if config_dirs & dirs:
        return "config"

    return "unknown"


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------


def run_tests(repo_dir: Path, project_type: str, custom_cmd: str = "") -> dict[str, Any]:
    """Run tests for the given project type. Returns result dict."""
    env = os.environ.copy()
    env["CI"] = "true"
    # Prevent prompts during install
    env["PYTHONUNBUFFERED"] = "1"
    env["NPM_CONFIG_YES"] = "true"

    def _run(cmd: list[str], timeout: int, cwd: Path | None = None) -> tuple[int, str, str, str]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or repo_dir,
                env=env,
            )
            return result.returncode, result.stdout, result.stderr, ""
        except subprocess.TimeoutExpired:
            return -1, "", f"Timeout after {timeout}s", "timeout"
        except FileNotFoundError as exc:
            return -2, "", str(exc), "tool_missing"

    if custom_cmd:
        rc, stdout, stderr, err = _run(custom_cmd.split(), TIMEOUT_TEST)
        return _build_result(rc, stdout, stderr, custom_cmd, error_type=err)

    if project_type == "bun":
        _run(["bun", "install"], TIMEOUT_INSTALL)
        rc, stdout, stderr, err = _run(["bun", "test"], TIMEOUT_TEST)
        return _build_result(rc, stdout, stderr, "bun test", error_type=err)

    if project_type == "npm":
        _run(["npm", "install", "--no-audit", "--no-fund"], TIMEOUT_INSTALL)
        rc, stdout, stderr, err = _run(["npm", "test"], TIMEOUT_TEST)
        return _build_result(rc, stdout, stderr, "npm test", error_type=err)

    if project_type == "python":
        # Try uv first, fall back to pip
        uv_ok, _, _, _ = _run(["uv", "sync"], 30, cwd=repo_dir)
        if uv_ok == 0:
            rc, stdout, stderr, err = _run(
                ["uv", "run", "pytest", "-q", "--tb=line"], TIMEOUT_TEST, cwd=repo_dir
            )
            return _build_result(rc, stdout, stderr, "uv run pytest", error_type=err)
        else:
            _run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], TIMEOUT_INSTALL)
            rc, stdout, stderr, err = _run(
                [sys.executable, "-m", "pytest", "-q", "--tb=line"], TIMEOUT_TEST
            )
            return _build_result(rc, stdout, stderr, "pytest", error_type=err)

    if project_type == "skill":
        # Single SKILL.md repo — use skill-quality for scoring
        skill_md = repo_dir / "SKILL.md"
        if not skill_md.exists():
            return _build_result(
                -1,
                "",
                "SKILL.md not found",
                "skill-quality",
                error_type="unknown_type",
            )
        # Prefer GitHub Models (free) when available, else keyword fallback
        gh_token = os.environ.get("GITHUB_TOKEN", "")
        cmd = ["uv", "run", "skill-quality", str(skill_md), "--output", "json"]
        if gh_token:
            cmd.append("--gh-models")
        rc, stdout, stderr, err = _run(cmd, TIMEOUT_TEST)
        return _build_result(rc, stdout, stderr, "skill-quality check", error_type=err)

    if project_type == "config":
        # Count and validate configuration files
        count_result = _count_config_files(repo_dir)
        return {
            "command": "config validation",
            "exit_code": 0,
            "test_count": count_result["total_files"],
            "passed": count_result["total_files"],
            "failed": 0,
            "errors": count_result["errors"],
            "stdout": json.dumps(count_result, indent=2),
            "stderr": "",
            "duration_ms": 0,
        }

    return _build_result(
        -1,
        "",
        f"Unknown project type: {project_type}",
        "unknown",
        error_type="unknown_type",
    )


def _count_config_files(repo_dir: Path) -> dict[str, object]:
    """Count agent/skill/command/rule files in a config-driven repo."""
    counts: dict[str, int] = {}
    errors = 0
    for dirname in ("agents", "skills", "commands", "rules", "hooks"):
        d = repo_dir / dirname
        if d.exists() and d.is_dir():
            # Count SKILL.md / YAML / Markdown files
            n = len(list(d.rglob("*")))
            counts[dirname] = n
        else:
            counts[dirname] = 0
    return {"counts": counts, "total_files": sum(counts.values()), "errors": errors}


def _build_result(
    rc: int,
    stdout: str,
    stderr: str,
    command: str,
    duration_ms: int = 0,
    error_type: str = "",
) -> dict[str, Any]:
    """Build a unified result dict from raw test output."""
    # Try to extract test counts from pytest/npm/bun output
    passed, failed, total = 0, 0, 0

    # skill-quality JSON output: {"overall_score": 0.53, "dimensions": [...]}
    if '"overall_score"' in stdout:
        try:
            import json as _json

            data = _json.loads(stdout)
            score = data.get("overall_score", 0)
            # Treat quality score as: pass if >= 0.5
            passed = 1 if score >= 0.5 else 0
            total = 1
            # Collect findings from LLM dimensions
            findings: list[str] = []
            for dim in data.get("dimensions", []):
                for f in dim.get("findings", []):
                    findings.append(f"[{dim.get('name', 'dim')}] {f}")
                for imp in dim.get("improvements", []):
                    findings.append(f"[{dim.get('name', 'dim')}] → {imp}")
            summary = data.get("summary", "")
            if summary:
                findings.insert(0, f"Summary: {summary}")

            return {
                "command": command,
                "exit_code": 0,
                "test_count": 1,
                "passed": passed,
                "failed": 1 - passed,
                "errors": 0,
                "stdout": f"Quality score: {score:.0%} ({score:.2f})",
                "stderr": stderr[-2000:] if len(stderr) > 2000 else stderr,
                "duration_ms": duration_ms,
                "error_type": error_type,
                "quality_score": score,
                "findings": findings,
            }
        except Exception:
            pass  # fall through to normal parsing

    # pytest: "5 passed", "2 failed"
    pytest_match = re.search(r"(\d+)\s+passed", stdout)
    if pytest_match:
        total = int(pytest_match.group(1))
        passed = int(pytest_match.group(1))
        fail_match = re.search(r"(\d+)\s+failed", stdout)
        if fail_match:
            failed = int(fail_match.group(1))
            total += failed

    # bun test: "5829 pass", "43 fail"
    bun_pass = re.search(r"(\d+)\s+pass", stdout)
    bun_fail = re.search(r"(\d+)\s+fail", stdout)
    if bun_pass:
        passed = int(bun_pass.group(1))
        total = passed
    if bun_fail:
        failed = int(bun_fail.group(1))
        total += failed

    # npm test: "(pass)" count
    if total == 0:
        npm_pass = len(re.findall(r"\(pass\)", stdout))
        npm_fail = len(re.findall(r"\(fail\)", stdout))
        if npm_pass or npm_fail:
            passed = npm_pass
            failed = npm_fail
            total = npm_pass + npm_fail

    return {
        "command": command,
        "exit_code": rc,
        "test_count": total,
        "passed": passed,
        "failed": failed,
        "errors": 1 if rc not in (0, -1, -2) else 0,
        "stdout": stdout[-4000:] if len(stdout) > 4000 else stdout,
        "stderr": stderr[-2000:] if len(stderr) > 2000 else stderr,
        "duration_ms": duration_ms,
        "error_type": error_type,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(
    repo_url: str,
    project_type: str,
    branch: str,
    result: dict[str, Any],
    duration_s: float,
) -> str:
    """Generate a Markdown test report for issue comment."""
    passed = result.get("passed", 0)
    failed = result.get("failed", 0)
    total = result.get("test_count", 0)
    exit_code = result.get("exit_code", -1)
    command = result.get("command", "unknown")

    pass_rate = f"{(passed / total * 100):.1f}%" if total > 0 else "N/A"
    quality_score = result.get("quality_score")

    lines = [
        f"## Test Report: {repo_url}",
        "",
        "| | |",
        "|---|---|",
        f"| **Repository** | [{repo_url}]({repo_url}) |",
        f"| **Branch** | `{branch}` |",
        f"| **Type** | `{project_type}` |",
        f"| **Command** | `{command}` |",
        f"| **Duration** | {duration_s:.1f}s |",
    ]

    # Quality score line for skill-type repos
    if quality_score is not None:
        label = "Good" if quality_score >= 0.7 else "Fair" if quality_score >= 0.5 else "Needs Work"
        lines.append(f"| **Quality Score** | {quality_score:.0%} ({label}) |")

    lines.append("")

    if exit_code == -1:
        error_type = result.get("error_type", "")
        if error_type == "unknown_type":
            lines.extend(
                [
                    "### Result: Project Type Unknown",
                    "",
                    f"Could not detect project type for `{project_type}`.",
                    "Supported types: Python, Node/npm, Bun, Config-driven.",
                ]
            )
        elif error_type == "clone_failed":
            lines.extend(
                [
                    "### Result: Clone Failed",
                    "",
                    f"Could not clone {repo_url}.",
                ]
            )
        else:
            lines.extend(
                [
                    "### Result: Timeout",
                    "",
                    f"Test execution exceeded the {TIMEOUT_TEST}s limit.",
                ]
            )
    elif exit_code == -2:
        lines.extend(
            [
                "### Result: Tool Missing",
                "",
                f"Required tool not found: {result.get('stderr', 'unknown')}",
            ]
        )
    elif exit_code != 0:
        lines.extend(
            [
                "### Result: Tests Failed",
                "",
                "| Passed | Failed | Total | Rate |",
                "|--------|--------|-------|------|",
                f"| {passed} | {failed} | {total} | {pass_rate} |",
            ]
        )
    elif quality_score is not None:
        lines.extend(
            [
                "### Result: Skill Quality Assessment",
                "",
                f"Quality score: **{quality_score:.0%}** ({quality_score:.2f}/1.00)",
            ]
        )
    else:
        if quality_score is not None:
            label = (
                "Good" if quality_score >= 0.7 else "Fair" if quality_score >= 0.5 else "Needs Work"
            )
            lines.extend(
                [
                    f"### Result: Skill Quality {label}",
                    "",
                    f"Quality score: **{quality_score:.0%}** ({quality_score:.2f}/1.00)",
                ]
            )
        else:
            lines.extend(
                [
                    "### Result: All Passed",
                    "",
                    "| Passed | Total | Rate |",
                    "|--------|-------|------|",
                    f"| {passed} | {total} | {pass_rate} |",
                ]
            )

    # Add improvements section if present
    improvements = [f for f in result.get("findings", []) if "→" in str(f)]
    if not improvements:
        # Try parsing from stdout for JSON-based checkers
        stdout = result.get("stdout", "")
        improvements = [ln for ln in stdout.split("\n") if "→" in ln]
    if improvements:
        lines.extend(
            [
                "",
                "### Suggestions for Improvement",
                "",
            ]
        )
        for i, imp in enumerate(improvements[:8]):  # top 8
            lines.append(f"{i + 1}. {imp.split('→', 1)[-1].strip()}")
        lines.append("")

    # Add stdout summary if tests ran
    stdout = result.get("stdout", "")
    if stdout and project_type != "config":
        lines.extend(
            [
                "",
                "<details>",
                "<summary>Test output (last 4000 chars)</summary>",
                "",
                "```",
                stdout[-2000:],
                "```",
                "",
                "</details>",
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "*Auto-generated by [agent-skill-infra](https://github.com/Liber1917/agent-skill-infra)*",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    trigger_source = os.environ.get("TRIGGER_SOURCE", "")
    is_dispatch = trigger_source == "workflow_dispatch"

    # Dispatch mode: read from workflow inputs
    if is_dispatch:
        repo_url = os.environ.get("REPO_URL", "")
        branch = os.environ.get("BRANCH", "main")
        custom_cmd = os.environ.get("TEST_COMMAND", "")
        if not repo_url:
            print("Error: REPO_URL not set", file=sys.stderr)
            return 1
        issue_number = ""  # no comment to post in dispatch mode
        print(f"[dispatch] Testing: {repo_url} @ {branch}")
    else:
        issue_number = os.environ.get("ISSUE_NUMBER", "")
        issue_body = os.environ.get("ISSUE_BODY", "")
        if not issue_number or not issue_body:
            print("Error: ISSUE_NUMBER or ISSUE_BODY not set", file=sys.stderr)
            return 1

        # Parse
        fields = parse_issue_body(issue_body)
        repo_url = fields.get("repo_url", "")
        branch = fields.get("branch", "main") or "main"
        custom_cmd = fields.get("test_command", "")

        if not repo_url:
            extracted = extract_repo_url(issue_body)
            if extracted:
                repo_url = f"https://github.com/{extracted[0]}/{extracted[1]}"
            else:
                _post_comment(issue_number, "Could not find a repository URL in the issue.")
                return 1

    print(f"Testing: {repo_url} @ {branch}")

    # Clone
    t0 = time.monotonic()
    target_dir = Path(tempfile.mkdtemp(prefix="skill-test-")) / "target"
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target_dir)],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        # Try without branch specification
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            branch = "default"
        except subprocess.CalledProcessError:
            _post_comment(issue_number, f"Failed to clone {repo_url}\n```\n{exc.stderr}\n```")
            return 1
    except subprocess.TimeoutExpired:
        _post_comment(issue_number, f"Clone timed out for {repo_url}")
        return 1

    # Detect
    project_type = detect_project_type(target_dir)
    print(f"Detected: {project_type}")

    # Test
    result = run_tests(target_dir, project_type, custom_cmd)
    duration = time.monotonic() - t0
    result["duration_ms"] = int(duration * 1000)

    # Report
    report = generate_report(repo_url, project_type, branch, result, duration)
    if is_dispatch:
        print(report)
    else:
        _post_comment(issue_number, report)

    # Exit code follows test result
    return 1 if result.get("failed", 0) > 0 or result.get("exit_code", 0) != 0 else 0


def _post_comment(issue_number: str, body: str) -> None:
    """Post a comment to the GitHub issue."""
    try:
        _gh_api("POST", f"issues/{issue_number}/comments", {"body": body})
        print(f"Comment posted on issue #{issue_number}")
    except Exception as exc:
        print(f"Failed to post comment: {exc}", file=sys.stderr)
        # Fallback: print for workflow log
        print(body)


if __name__ == "__main__":
    sys.exit(main())
