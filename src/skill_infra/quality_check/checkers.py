"""Quality sub-checkers: trigger, output, tolerance, token, helloandy."""

from __future__ import annotations

import re

from skill_infra.quality_check.parser import ParsedSkill
from skill_infra.quality_check.scorecard import DimensionScore


class TriggerChecker:
    """Check trigger precision: is the description specific enough?"""

    _DIM_NAME = "trigger_precision"
    _KEYWORD_PATTERN = re.compile(r"[a-zA-Z]{3,}")

    def check(self, parsed: ParsedSkill) -> DimensionScore:
        desc = parsed.meta.description.strip()
        findings: list[str] = []

        if not desc:
            return DimensionScore(
                name=self._DIM_NAME,
                score=0.0,
                findings=["Description is empty"],
            )

        # Count meaningful keywords
        keywords = self._KEYWORD_PATTERN.findall(desc)
        keyword_count = len(set(kw.lower() for kw in keywords))

        # Check for specificity signals
        has_domain_terms = any(
            term in desc.lower()
            for term in [
                "using",
                "via",
                "with",
                "for",
                "analyze",
                "generate",
                "create",
                "optimize",
                "check",
                "validate",
            ]
        )

        if keyword_count >= 5 and has_domain_terms:
            score = 0.9
            findings.append("Good keyword coverage with domain-specific terms")
        elif keyword_count >= 3:
            score = 0.6
            findings.append("Moderate keyword coverage")
        else:
            score = 0.3
            findings.append("Description too vague, add more specific keywords")

        # Check for anti-patterns
        if desc.lower() in ("a helpful tool", "a tool", "help", "utility"):
            score = min(score, 0.1)
            findings.append("Description is too generic")

        if len(desc) < 20:
            score = min(score, 0.2)
            findings.append("Description too short (<20 chars)")

        return DimensionScore(name=self._DIM_NAME, score=score, findings=findings)


class OutputChecker:
    """Check output completeness: format, examples, constraints defined?"""

    _DIM_NAME = "output_completeness"

    def check(self, parsed: ParsedSkill) -> DimensionScore:
        body = parsed.raw_body.lower()
        findings: list[str] = []
        score = 0.0

        has_format = any(
            kw in body for kw in ["output format", "output:", "## output", "return", "response"]
        )
        has_examples = any(
            kw in body for kw in ["example", "## example", "sample", "```", "output example"]
        )
        has_constraints = any(
            kw in body for kw in ["constraint", "limit", "must", "should not", "maximum"]
        )

        if has_format:
            score += 0.4
            findings.append("Output format is defined")
        else:
            findings.append("No output format section found")

        if has_examples:
            score += 0.3
            findings.append("Examples provided")
        else:
            findings.append("No examples found")

        if has_constraints:
            score += 0.3
            findings.append("Output constraints defined")
        else:
            findings.append("Consider adding output constraints")

        return DimensionScore(name=self._DIM_NAME, score=min(score, 1.0), findings=findings)


class ToleranceChecker:
    """Check error recovery coverage: try/catch, fallback, retry logic."""

    _DIM_NAME = "error_recovery"

    def check(self, parsed: ParsedSkill) -> DimensionScore:
        body = parsed.raw_body.lower()
        findings: list[str] = []
        score = 0.0

        error_keywords = [
            "error",
            "fail",
            "not found",
            "unavailable",
            "exception",
            "timeout",
            "retry",
            "fallback",
            "skip",
            "continue",
            "graceful",
            "recover",
            "handle",
            "try again",
            "if not",
        ]

        matches = [kw for kw in error_keywords if kw in body]
        match_count = len(matches)

        if match_count >= 4:
            score = 0.9
            findings.append(f"Good error handling coverage ({match_count} signals)")
        elif match_count >= 2:
            score = 0.6
            findings.append(f"Moderate error handling ({match_count} signals)")
        elif match_count >= 1:
            score = 0.3
            findings.append(f"Minimal error handling ({match_count} signal)")
        else:
            score = 0.0
            findings.append("No error handling detected")

        return DimensionScore(name=self._DIM_NAME, score=score, findings=findings)


class TokenChecker:
    """Check token efficiency: total lines, content length."""

    _DIM_NAME = "token_efficiency"
    _MAX_LINES = 500

    def check(self, parsed: ParsedSkill) -> DimensionScore:
        total = parsed.total_lines
        findings: list[str] = []

        if total == 0:
            return DimensionScore(
                name=self._DIM_NAME, score=1.0, findings=["Empty file, no token concerns"]
            )

        if total <= 200:
            score = 1.0
            findings.append(f"Compact ({total} lines)")
        elif total <= self._MAX_LINES:
            ratio = total / self._MAX_LINES
            score = 0.8
            findings.append(f"Acceptable length ({total} lines)")
            if ratio > 0.8:
                findings.append("Approaching 500-line limit, consider splitting")
        else:
            overshoot = total - self._MAX_LINES
            score = max(0.0, 1.0 - (overshoot / self._MAX_LINES))
            findings.append(f"Exceeds {self._MAX_LINES} lines by {overshoot}")
            findings.append("Consider splitting content into references/ files")

        return DimensionScore(name=self._DIM_NAME, score=score, findings=findings)


class HelloAndyChecker:
    """Composite 8-dimension checker based on helloandy quality rubric.

    Dimensions: trigger_precision, output_completeness, rule_specificity,
    error_recovery, example_quality, conciseness, consistency, edge_cases.
    """

    _DIM_NAME = "helloandy_8dim"

    def __init__(self) -> None:
        self._trigger = TriggerChecker()
        self._output = OutputChecker()
        self._tolerance = ToleranceChecker()
        self._token = TokenChecker()

    def check(self, parsed: ParsedSkill) -> DimensionScore:
        """Run all 8 sub-dimensions and return composite score."""
        sub_scores: list[float] = []
        all_findings: list[str] = []

        # Dimension 1: Trigger precision (delegated)
        t = self._trigger.check(parsed)
        sub_scores.append(t.score)
        all_findings.extend(f"[trigger] {f}" for f in t.findings)

        # Dimension 2: Output completeness (delegated)
        o = self._output.check(parsed)
        sub_scores.append(o.score)
        all_findings.extend(f"[output] {f}" for f in o.findings)

        # Dimension 3: Rule specificity (check for concrete rules)
        rule_score, rule_findings = self._check_rule_specificity(parsed)
        sub_scores.append(rule_score)
        all_findings.extend(f"[rules] {f}" for f in rule_findings)

        # Dimension 4: Error recovery (delegated)
        e = self._tolerance.check(parsed)
        sub_scores.append(e.score)
        all_findings.extend(f"[error] {f}" for f in e.findings)

        # Dimension 5: Example quality
        ex_score, ex_findings = self._check_examples(parsed)
        sub_scores.append(ex_score)
        all_findings.extend(f"[examples] {f}" for f in ex_findings)

        # Dimension 6: Conciseness (delegated to token checker)
        c = self._token.check(parsed)
        sub_scores.append(c.score)
        all_findings.extend(f"[concise] {f}" for f in c.findings)

        # Dimension 7: Consistency
        con_score, con_findings = self._check_consistency(parsed)
        sub_scores.append(con_score)
        all_findings.extend(f"[consistency] {f}" for f in con_findings)

        # Dimension 8: Edge cases
        edge_score, edge_findings = self._check_edge_cases(parsed)
        sub_scores.append(edge_score)
        all_findings.extend(f"[edge] {f}" for f in edge_findings)

        overall = sum(sub_scores) / len(sub_scores) if sub_scores else 0.0

        return DimensionScore(
            name=self._DIM_NAME,
            score=overall,
            findings=all_findings,
        )

    @staticmethod
    def _check_rule_specificity(parsed: ParsedSkill) -> tuple[float, list[str]]:
        body = parsed.raw_body.lower()
        findings: list[str] = []
        score = 0.0

        has_must = "must" in body or "required" in body
        has_never = "never" in body or "must not" in body or "do not" in body
        has_steps = "step" in body or "1." in body or "first" in body

        if has_must:
            score += 0.4
            findings.append("Has mandatory rules")
        if has_never:
            score += 0.3
            findings.append("Has forbidden actions")
        if has_steps:
            score += 0.3
            findings.append("Has step-by-step instructions")

        if score == 0.0:
            findings.append("No concrete rules found")

        return min(score, 1.0), findings

    @staticmethod
    def _check_examples(parsed: ParsedSkill) -> tuple[float, list[str]]:
        body = parsed.raw_body
        findings: list[str] = []
        score = 0.0

        has_example_section = "## example" in body.lower() or "## Examples" in body
        has_code_block = "```" in body
        has_input_output = "input:" in body.lower() or "output:" in body.lower()

        if has_example_section:
            score += 0.4
            findings.append("Has example section")
        if has_code_block:
            score += 0.3
            findings.append("Has code blocks")
        if has_input_output:
            score += 0.3
            findings.append("Has input/output examples")

        if score == 0.0:
            findings.append("No examples found")

        return min(score, 1.0), findings

    @staticmethod
    def _check_consistency(parsed: ParsedSkill) -> tuple[float, list[str]]:
        findings: list[str] = []

        # Check that description and section titles are consistent
        desc_lower = parsed.meta.description.lower()
        sections = parsed.sections
        body_lower = parsed.raw_body.lower()

        if desc_lower and sections:
            # At least check basic consistency: no contradictions
            score = 0.8
            findings.append("Basic consistency check passed")
        else:
            score = 0.5
            findings.append("Cannot check consistency (missing description or sections)")

        # Check for contradictory statements (simple heuristic)
        if "always" in body_lower and "never" in body_lower:
            score = min(score, 0.5)
            findings.append("Contains both 'always' and 'never' - may be contradictory")

        return score, findings

    @staticmethod
    def _check_edge_cases(parsed: ParsedSkill) -> tuple[float, list[str]]:
        body = parsed.raw_body.lower()
        findings: list[str] = []
        score = 0.0

        edge_keywords = [
            "edge case",
            "if not",
            "empty",
            "null",
            "none",
            "timeout",
            "invalid",
            "malformed",
            "missing",
            "fallback",
            "default",
        ]

        matches = [kw for kw in edge_keywords if kw in body]
        match_count = len(matches)

        if match_count >= 3:
            score = 0.9
            findings.append(f"Good edge case coverage ({match_count} signals)")
        elif match_count >= 1:
            score = 0.5
            findings.append(f"Some edge case handling ({match_count} signals)")
        else:
            score = 0.1
            findings.append("No edge case handling detected")

        return score, findings
