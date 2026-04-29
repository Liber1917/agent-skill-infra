"""Version awareness: diff analysis, regression detection, and security scanning."""

from skill_infra.version_aware.git_diff import FileDiff, VersionDiff, parse_version_diff
from skill_infra.version_aware.regression import RegressionDetector, RegressionReport
from skill_infra.version_aware.rollback import get_previous_sha, rollback_to
from skill_infra.version_aware.security_diff import (
    SecurityDiffAnalyzer,
    SecurityDiffReport,
    SecurityFinding,
)

__all__ = [
    "FileDiff",
    "RegressionDetector",
    "RegressionReport",
    "SecurityDiffAnalyzer",
    "SecurityDiffReport",
    "SecurityFinding",
    "VersionDiff",
    "get_previous_sha",
    "parse_version_diff",
    "rollback_to",
]
