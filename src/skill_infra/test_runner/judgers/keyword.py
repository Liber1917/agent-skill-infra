"""KeywordJudger: checks whether the output contains expected keywords."""

from __future__ import annotations

from skill_infra.test_runner.judgers.base import Judger


class KeywordJudger(Judger):
    """Keyword presence judger.

    Expected dict format::

        {
            "keywords": ["keyword1", "keyword2"],
            "mode": "any" | "all",   # default: "any"
            "threshold": 0.5          # default: 0.5 (for "any" mode)
        }

    Score is the fraction of keywords found in the output (case-insensitive).
    In "all" mode, passed = score == 1.0.
    In "any" mode, passed = score >= threshold.
    """

    def judge(self, output: str, expected: dict) -> tuple[bool, float, str]:  # type: ignore[type-arg]
        keywords: list[str] = expected.get("keywords", [])
        mode: str = expected.get("mode", "any")
        threshold: float = float(expected.get("threshold", 0.5))

        if not keywords:
            return True, 1.0, "no keywords specified"

        output_lower = output.lower()
        matched = [kw for kw in keywords if kw.lower() in output_lower]
        score = len(matched) / len(keywords)

        if mode == "all":
            passed = score == 1.0
            reason = (
                f"all {len(keywords)} keywords matched"
                if passed
                else f"{len(matched)}/{len(keywords)} keywords matched"
            )
        else:
            passed = score >= threshold
            reason = (
                f"{len(matched)}/{len(keywords)} keywords matched"
                if matched
                else "no keywords matched"
            )

        return passed, score, reason
