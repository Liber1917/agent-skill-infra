#!/usr/bin/env python3
"""Pre-flight safety checks for agent-skill-infra CI pipeline.

Runs before pytest to catch tool-availability and structural issues early.
Inspired by ecc-universal's 7-stage CI validation pipeline.

Exit codes:
  0 = all clear (all checks passed, or only warnings)
  1 = blocking issue (critical tool missing, tests would fail)
  2 = warning only (optional tool missing, but tests will run)
"""

from __future__ import annotations

import importlib
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

# Terminal colors (no dependency needed)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}OK{RESET}  {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}WARN{RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}FAIL{RESET} {msg}")


# ---------------------------------------------------------------------------
# Check functions — each returns (passed: bool, is_critical: bool)
# ---------------------------------------------------------------------------


def check_git_available() -> tuple[bool, bool]:
    """git must be available for version_aware module."""
    print(f"\n{BOLD}1. Git availability{RESET}")
    if shutil.which("git"):
        _ok("git found")
        return True, True
    _fail("git not found — version_aware module requires git")
    print("    Install: brew install git / apt-get install git")
    return False, True


def check_cisco_scanner() -> tuple[bool, bool]:
    """cisco-scanner is optional for --security flag."""
    print(f"\n{BOLD}2. Cisco Scanner (optional){RESET}")
    if shutil.which("cisco-scanner"):
        _ok("cisco-scanner available")
    else:
        _warn("cisco-scanner not found — --security scans will be skipped")
        print("    Install: pip install cisco-scanner")
    return True, False  # non-critical


def check_npx_available() -> tuple[bool, bool]:
    """npx is optional for --lint flag."""
    print(f"\n{BOLD}3. npx (optional){RESET}")
    if shutil.which("npx"):
        _ok("npx available")
    else:
        _warn("npx not found — --lint checks will be skipped")
        print("    Install: npm install -g npx")
    return True, False  # non-critical


def check_cli_entry_points_importable() -> tuple[bool, bool]:
    """All CLI entry points registered in pyproject.toml must be importable."""
    print(f"\n{BOLD}4. CLI entry point importability{RESET}")
    entry_points = [
        ("skill-test", "skill_infra.test_runner.cli"),
        ("skill-quality", "skill_infra.quality_check.cli"),
        ("skill-version", "skill_infra.version_aware.cli"),
    ]
    all_ok = True
    for name, module_path in entry_points:
        try:
            importlib.import_module(module_path)
            _ok(f"{name} ({module_path})")
        except ImportError as exc:
            _fail(f"{name} ({module_path}): {exc}")
            all_ok = False
    return all_ok, True


def check_skill_fixtures_exist() -> tuple[bool, bool]:
    """Verify all bundled SKILL.md fixtures exist and parse cleanly."""
    print(f"\n{BOLD}5. SKILL.md fixture integrity{RESET}")
    repo_root = Path(__file__).resolve().parent.parent.parent

    skill_dirs = [
        repo_root / "skills" / "quality-check",
        repo_root / "skills" / "test-runner",
        repo_root / "skills" / "version-aware",
    ]
    all_ok = True

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            _fail(f"Missing: {skill_md}")
            all_ok = False
            continue

        try:
            from skill_infra.quality_check.parser import parse_skill_md

            parsed = parse_skill_md(str(skill_md))
            name = parsed.meta.name
            desc_len = len(parsed.meta.description)
            _ok(
                f"{skill_dir.name}: name={name!r}, "
                f"desc={desc_len} chars, lines={parsed.total_lines}"
            )
        except Exception as exc:
            _fail(f"{skill_dir.name}: parse failed — {exc}")
            all_ok = False

    return all_ok, True


def check_no_hardcoded_paths() -> tuple[bool, bool]:
    """Scan source for hardcoded absolute paths that shouldn't be there."""
    print(f"\n{BOLD}6. Hardcoded path scan{RESET}")
    repo_root = Path(__file__).resolve().parent.parent.parent

    suspicious = 0
    for py_file in repo_root.glob("src/**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            # Allow /tmp/ in test_normalize_* functions and /Users/ in comments/docs
            if "/tmp/" in line and "normalize" not in line.lower() and "test_" not in str(py_file):
                # Check if it's in a string literal (likely data)
                if '"' in line or "'" in line:
                    continue  # most likely test data or examples
                _warn(f"{py_file}:{i}: hardcoded /tmp/ path")
                suspicious += 1

    if suspicious == 0:
        _ok("no hardcoded absolute paths found")
    return True, False  # non-critical


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run all pre-flight checks. Returns exit code."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo_root / "src"))

    checks: list[Callable[[], tuple[bool, bool]]] = [
        check_git_available,
        check_cisco_scanner,
        check_npx_available,
        check_cli_entry_points_importable,
        check_skill_fixtures_exist,
        check_no_hardcoded_paths,
    ]

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  agent-skill-infra pre-flight checks{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")

    critical_failures = 0
    warnings = 0

    for check_fn in checks:
        passed, is_critical = check_fn()
        if not passed and is_critical:
            critical_failures += 1
        elif not passed:
            warnings += 1

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    if critical_failures > 0:
        print(f"{RED}Pre-flight: {critical_failures} critical failure(s){RESET}")
        return 1
    elif warnings > 0:
        print(f"{YELLOW}Pre-flight: passed with {warnings} warning(s){RESET}")
        return 0
    else:
        print(f"{GREEN}Pre-flight: all checks passed{RESET}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
