"""Security diff analyzer: detect security-relevant changes between versions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

from skill_infra.version_aware.git_diff import parse_version_diff

# Security-sensitive patterns: (pattern, severity, description)
_SECURITY_PATTERNS: list[tuple[str, str, str]] = [
    # High severity: destructive commands
    (r"\brm\s+-rf\b", "high", "Destructive rm -rf detected"),
    (r"\bchmod\s+777\b", "high", "Insecure file permissions (chmod 777)"),
    (r"\bsudo\b", "high", "Privilege escalation (sudo)"),
    (r"\bmkfs\b", "high", "Filesystem formatting command"),
    (r"\bdd\s+.*of=/dev/", "high", "Direct device write (dd)"),
    (r">\s*/dev/", "high", "Direct device write redirection"),
    # Medium severity: network access
    (r"\bcurl\b", "medium", "Network request via curl"),
    (r"\bwget\b", "medium", "Network request via wget"),
    (r"\brequests?\.(get|post|put|delete|patch)\b", "medium", "HTTP request via Python"),
    (r"\bfetch\s*\(", "medium", "Network request via fetch"),
    (r"\bPOST\b.*https?://", "medium", "HTTP POST to external URL"),
    # Medium severity: file system access
    (r"/etc/(passwd|shadow|hosts)", "medium", "Access to system config files"),
    (r"~/.ssh/", "medium", "Access to SSH directory"),
    (r"\bcp\s+.*~/.ssh/", "high", "SSH key exfiltration attempt"),
    (r"\bcat\s+/etc/", "medium", "Reading system files"),
    # Low severity: environment and eval
    (r"\beval\s*\(", "medium", "Dynamic code execution (eval)"),
    (r"\bexec\s*\(", "medium", "Dynamic code execution (exec)"),
    (r"\bos\.system\b", "medium", "System command execution"),
    (r"\bsubprocess\b", "low", "Subprocess invocation"),
    (r"\b__import__\b", "medium", "Dynamic module import"),
    (r"environ", "low", "Environment variable access"),
    # Low severity: encoding/obfuscation signals
    (r"\bbase64\b", "low", "Base64 encoding/decoding"),
    (r"\bopenssl\b", "low", "OpenSSL command"),
]


@dataclass
class SecurityFinding:
    """A single security-relevant finding in a diff."""

    pattern: str
    severity: str  # "high" | "medium" | "low"
    description: str
    file_path: str
    context: str  # Surrounding diff lines for context


@dataclass
class SecurityDiffReport:
    """Aggregated security analysis of a version diff."""

    has_security_changes: bool
    max_severity: str  # "none" | "low" | "medium" | "high"
    findings: list[SecurityFinding] = field(default_factory=list)

    _SEVERITY_ORDER: ClassVar[dict[str, int]] = {"none": 0, "low": 1, "medium": 2, "high": 3}

    def _update_max_severity(self) -> None:
        if not self.findings:
            self.max_severity = "none"
            self.has_security_changes = False
        else:
            self.has_security_changes = True
            max_sev = max(self.findings, key=lambda f: self._SEVERITY_ORDER.get(f.severity, 0))
            self.max_severity = max_sev.severity


class SecurityDiffAnalyzer:
    """Analyze git diffs for security-relevant changes.

    Detects introduction of dangerous commands, network access,
    file system access, and privilege escalation patterns.
    """

    def __init__(
        self,
        extra_patterns: list[tuple[str, str, str]] | None = None,
    ) -> None:
        self._patterns = list(_SECURITY_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

    def analyze(
        self,
        repo_path: str,
        old_ref: str,
        new_ref: str,
    ) -> SecurityDiffReport:
        """Analyze the diff between two refs for security changes.

        Args:
            repo_path: Path to the git repository.
            old_ref: Old commit SHA or ref.
            new_ref: New commit SHA or ref.

        Returns:
            SecurityDiffReport with findings and severity assessment.
        """
        version_diff = parse_version_diff(repo_path, old_ref, new_ref)

        findings: list[SecurityFinding] = []

        for file_diff in version_diff.files:
            # Only check added lines (+ lines in the patch)
            added_lines = self._extract_added_lines(file_diff.patch)

            for line_text in added_lines:
                for pattern_str, severity, description in self._patterns:
                    if re.search(pattern_str, line_text, re.IGNORECASE):
                        findings.append(
                            SecurityFinding(
                                pattern=pattern_str,
                                severity=severity,
                                description=description,
                                file_path=file_diff.path,
                                context=line_text.strip(),
                            )
                        )

        # Deduplicate findings (same pattern + same file)
        seen: set[tuple[str, str, str]] = set()
        unique_findings: list[SecurityFinding] = []
        for f in findings:
            key = (f.pattern, f.file_path, f.context[:50])
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        report = SecurityDiffReport(
            has_security_changes=False,
            max_severity="none",
            findings=unique_findings,
        )
        report._update_max_severity()
        return report

    @staticmethod
    def _extract_added_lines(patch: str) -> list[str]:
        """Extract added lines from a unified diff patch."""
        lines: list[str] = []
        for line in patch.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(line[1:])  # Strip the leading '+'
        return lines
