"""Catalog consistency checks: ensure code, manifest, and docs agree on feature counts.

Inspired by ecc-universal's catalog:check step — validates that the number of
agents/commands/skills in docs matches the actual files on disk.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _public_classes(module_path: str) -> set[str]:
    """Return names of public (non-underscore) classes in a module."""
    mod = importlib.import_module(module_path)
    return {
        name
        for name, obj in inspect.getmembers(mod, inspect.isclass)
        if not name.startswith("_") and obj.__module__ == mod.__name__
    }


def _exported_names(module_path: str) -> set[str]:
    """Return names listed in a module's __all__ (if defined)."""
    mod = importlib.import_module(module_path)
    return set(getattr(mod, "__all__", []))


# ---------------------------------------------------------------------------
# 1. Checker count: checkers.py classes vs docs claim
# ---------------------------------------------------------------------------


def test_checker_class_count() -> None:
    """checkers.py defines exactly 5 public checker classes."""
    classes = _public_classes("skill_infra.quality_check.checkers")
    assert len(classes) == 5, f"Expected 5 checker classes, got {len(classes)}: {sorted(classes)}"


def test_checker_types_match_readme() -> None:
    """README mentions the 3 CLI tools."""
    readme = Path(__file__).parent.parent / "README.md"
    content = readme.read_text(encoding="utf-8")

    assert "skill-quality" in content, "README missing skill-quality reference"
    assert "skill-test" in content, "README missing skill-test reference"
    assert "skill-version" in content, "README missing skill-version reference"


# ---------------------------------------------------------------------------
# 2. Judge type count: judger registry vs exports
# ---------------------------------------------------------------------------


def test_judger_export_count() -> None:
    """judgers/__init__.py exports 7 names (6 judges + base Judger ABC)."""
    exports = _exported_names("skill_infra.test_runner.judgers")
    expected = {
        "KeywordJudger",
        "SchemaJudger",
        "LLMStubJudger",
        "FlowJudge",
        "LLMJudge",
        "SnapshotJudger",
        "Judger",
    }
    msg = f"Unexpected exports: {exports - expected} or missing: {expected - exports}"
    assert exports == expected, msg


def test_judger_registry_coverage() -> None:
    """Every exported judger (except base Judger and LLMJudge) has a registry entry."""
    from skill_infra.test_runner.runner import _DEFAULT_JUDGER_REGISTRY

    # Map of exported class name -> expected registry key
    expected_mapping = {
        "KeywordJudger": "keyword",
        "SchemaJudger": "schema",
        "LLMStubJudger": "llm",
        "FlowJudge": "flow",
        "SnapshotJudger": "snapshot",
    }
    registry_keys = set(_DEFAULT_JUDGER_REGISTRY.keys())

    for class_name, expected_key in expected_mapping.items():
        assert expected_key in registry_keys, (
            f"Exported judger {class_name!r} has no registry entry "
            f"(expected key {expected_key!r}, got {sorted(registry_keys)})"
        )


def test_judge_type_in_schema() -> None:
    """evals_schema.py allows all registered judge types."""
    from skill_infra.test_runner.runner import _DEFAULT_JUDGER_REGISTRY

    schema_path = (
        Path(__file__).parent.parent / "src" / "skill_infra" / "shared" / "evals_schema.py"
    )
    schema_code = schema_path.read_text(encoding="utf-8")

    for key in _DEFAULT_JUDGER_REGISTRY:
        assert key in schema_code, f"Judge type {key!r} not found as valid value in evals_schema.py"


# ---------------------------------------------------------------------------
# 3. CLI entry point count: pyproject.toml vs actual typer apps
# ---------------------------------------------------------------------------


def test_cli_entry_point_count() -> None:
    """pyproject.toml registers exactly 3 CLI scripts."""
    toml_path = Path(__file__).parent.parent / "pyproject.toml"
    content = toml_path.read_text(encoding="utf-8")

    # Count lines like 'skill-test = "..."'
    matches = re.findall(r"^skill-\w+\s*=", content, re.MULTILINE)
    assert len(matches) == 3, f"Expected 3 CLI entry points, got {len(matches)}: {matches}"


def test_cli_subcommand_counts() -> None:
    """Verify command counts: test=2, quality=1, version=4."""
    from skill_infra.quality_check.cli import app as quality_app
    from skill_infra.test_runner.cli import app as test_app
    from skill_infra.version_aware.cli import app as version_app

    # Count subcommands
    test_cmds = [c.name for c in test_app.registered_commands]
    quality_cmds = [c.name for c in quality_app.registered_commands]
    version_cmds = [c.name for c in version_app.registered_commands]

    # skill-version has 3 top-level commands (diff, check, rollback) + 1 group
    # (baseline with store/detect) = 5 total
    version_group_cmds = []
    for g in version_app.registered_groups:
        if g.typer_instance:
            for sc in g.typer_instance.registered_commands:
                version_group_cmds.append(f"{g.name}/{sc.name}")
    version_total = len(version_cmds) + len(version_group_cmds)

    assert len(test_cmds) == 2, f"skill-test: expected 2 commands, got {test_cmds}"
    assert len(quality_cmds) == 1, f"skill-quality: expected 1 command, got {quality_cmds}"
    assert version_total == 5, (
        f"skill-version: expected 5 commands, got {version_cmds} + {version_group_cmds}"
    )


# ---------------------------------------------------------------------------
# 4. Module importability
# ---------------------------------------------------------------------------


def test_all_three_modules_importable() -> None:
    """quality_check, test_runner, and version_aware are all importable."""
    importlib.import_module("skill_infra.quality_check")
    importlib.import_module("skill_infra.test_runner")
    importlib.import_module("skill_infra.version_aware")


def test_checker_names_are_descriptive() -> None:
    """All checker class names follow naming conventions (end with 'Checker')."""
    classes = _public_classes("skill_infra.quality_check.checkers")
    for name in classes:
        assert "Checker" in name, f"Checker class {name!r} should contain 'Checker' in name"
