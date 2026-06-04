from mapper_copilot.models import Mapping


class StubSuggester:
    def __init__(self, suggestions: dict[str, str]):
        self.suggestions = suggestions
        self.calls: list[str] = []

    def suggest(self, rsc_question: str) -> Mapping:
        self.calls.append(rsc_question)
        return Mapping(
            rsc_question=rsc_question,
            mapped_to=self.suggestions.get(rsc_question, ""),
            confidence=0.8,
            rule="Match the closest SLCP question.",
            source_candidates=list(self.suggestions.values()),
        )


def test_evaluate_single_exact_match():
    from mapper_copilot.evaluation import EvaluationHarness

    harness = EvaluationHarness(
        StubSuggester({"license": "Operating license/registration is available and up to date"})
    )

    assert (
        harness.evaluate_single(
            "license", "Operating license/registration is available and up to date"
        )
        is True
    )


def test_evaluate_single_case_insensitive():
    from mapper_copilot.evaluation import EvaluationHarness

    harness = EvaluationHarness(
        StubSuggester({"license": "OPERATING LICENSE/REGISTRATION IS AVAILABLE AND UP TO DATE"})
    )

    assert (
        harness.evaluate_single(
            "license", "Operating license/registration is available and up to date"
        )
        is True
    )


def test_evaluate_single_substring_match():
    from mapper_copilot.evaluation import EvaluationHarness

    harness = EvaluationHarness(StubSuggester({"license": "Operating license/registration"}))

    assert (
        harness.evaluate_single(
            "license", "Operating license/registration is available and up to date"
        )
        is True
    )


def test_evaluate_single_no_match():
    from mapper_copilot.evaluation import EvaluationHarness

    harness = EvaluationHarness(StubSuggester({"license": "Worker contracts are maintained"}))

    assert (
        harness.evaluate_single(
            "license", "Operating license/registration is available and up to date"
        )
        is False
    )


def test_evaluate_batch():
    from mapper_copilot.evaluation import EvaluationHarness

    suggester = StubSuggester(
        {
            "license": "Operating license/registration is available and up to date",
            "exits": "Emergency exits are clearly marked and unobstructed",
            "contracts": "Payroll records are complete",
        }
    )
    harness = EvaluationHarness(suggester)

    result = harness.evaluate(
        [
            {
                "rsc_question": "license",
                "expected_slcp_question": "Operating license/registration is available and up to date",
            },
            {
                "rsc_question": "exits",
                "expected_slcp_question": "Emergency exits are clearly marked and unobstructed",
            },
            {
                "rsc_question": "contracts",
                "expected_slcp_question": "Worker contracts are maintained and signed",
            },
        ]
    )

    assert suggester.calls == ["license", "exits", "contracts"]
    assert [detail["match"] for detail in result.details] == [True, True, False]


def test_evaluate_result_structure():
    from mapper_copilot.evaluation import EvaluationHarness, EvaluationResult

    harness = EvaluationHarness(
        StubSuggester({"license": "Operating license/registration is available and up to date"})
    )

    result = harness.evaluate(
        [
            {
                "rsc_question": "license",
                "expected_slcp_question": "Operating license/registration is available and up to date",
            }
        ]
    )

    assert isinstance(result, EvaluationResult)
    assert result.total == 1
    assert result.correct == 1
    assert result.accuracy == 1.0
    assert result.details == [
        {
            "rsc": "license",
            "expected": "Operating license/registration is available and up to date",
            "suggested": "Operating license/registration is available and up to date",
            "match": True,
        }
    ]


def test_evaluate_batch_accuracy_calculation():
    from mapper_copilot.evaluation import EvaluationHarness

    harness = EvaluationHarness(
        StubSuggester(
            {
                "one": "match one",
                "two": "wrong",
                "three": "match three",
            }
        )
    )

    result = harness.evaluate(
        [
            {"rsc_question": "one", "expected_slcp_question": "match one"},
            {"rsc_question": "two", "expected_slcp_question": "match two"},
            {"rsc_question": "three", "expected_slcp_question": "match three"},
        ]
    )

    assert result.correct == 2
    assert result.total == 3
    assert result.accuracy == 2 / 3


def test_evaluate_handles_empty_test_cases():
    from mapper_copilot.evaluation import EvaluationHarness

    harness = EvaluationHarness(StubSuggester({}))

    result = harness.evaluate([])

    assert result.total == 0
    assert result.correct == 0
    assert result.accuracy == 0.0
    assert result.details == []
