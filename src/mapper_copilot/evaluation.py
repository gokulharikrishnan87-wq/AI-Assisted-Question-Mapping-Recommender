"""Evaluation helpers for measuring suggester accuracy."""

from __future__ import annotations

from typing import Dict, List, Tuple

from pydantic import BaseModel, Field

from mapper_copilot.core.suggester import Suggester


class EvaluationResult(BaseModel):
    """Aggregate evaluation metrics and per-case details."""

    total: int = Field(..., description="Number of test cases")
    correct: int = Field(..., description="Number of correct mappings")
    accuracy: float = Field(..., description="Accuracy from 0.0 to 1.0")
    details: List[Dict] = Field(..., description="Per-case evaluation details")


class EvaluationHarness:
    """Measure suggester output against ground truth mappings."""

    def __init__(self, suggester: Suggester):
        """Initialize with a suggester."""
        self.suggester = suggester

    def evaluate(self, test_cases: List[Dict]) -> EvaluationResult:
        """Evaluate suggester against test cases."""
        details = []
        correct = 0

        for case in test_cases:
            rsc_question = case["rsc_question"]
            expected_slcp = case["expected_slcp_question"]
            suggested_slcp, match = self._evaluate_case(rsc_question, expected_slcp)
            if match:
                correct += 1
            details.append(
                {
                    "rsc": rsc_question,
                    "expected": expected_slcp,
                    "suggested": suggested_slcp,
                    "match": match,
                }
            )

        total = len(test_cases)
        accuracy = correct / total if total else 0.0
        return EvaluationResult(total=total, correct=correct, accuracy=accuracy, details=details)

    def evaluate_single(self, rsc_question: str, expected_slcp: str) -> bool:
        """Check if suggestion matches expected SLCP."""
        _, match = self._evaluate_case(rsc_question, expected_slcp)
        return match

    def _evaluate_case(self, rsc_question: str, expected_slcp: str) -> Tuple[str, bool]:
        mapping = self.suggester.suggest(rsc_question)
        suggested_slcp = mapping.mapped_to
        return suggested_slcp, self._matches_expected(suggested_slcp, expected_slcp)

    @staticmethod
    def _matches_expected(suggested_slcp: str, expected_slcp: str) -> bool:
        normalized_suggested = suggested_slcp.strip().lower()
        normalized_expected = expected_slcp.strip().lower()

        if not normalized_suggested or not normalized_expected:
            return False

        return (
            normalized_suggested == normalized_expected
            or normalized_suggested in normalized_expected
            or normalized_expected in normalized_suggested
        )
