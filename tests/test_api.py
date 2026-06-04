from fastapi.testclient import TestClient
import pytest

from mapper_copilot.api import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_info_endpoint(client: TestClient) -> None:
    response = client.get("/info")

    assert response.status_code == 200
    assert response.json() == {
        "version": "1.0.0",
        "description": "RSC to SLCP question mapper",
    }


def test_suggest_single_question(client: TestClient) -> None:
    question = "The facility has a business license for legal operation."

    response = client.post("/suggest", json={"rsc_question": question})

    assert response.status_code == 200
    payload = response.json()
    assert payload["rsc_question"] == question
    assert isinstance(payload["mapped_to"], str)
    assert payload["mapped_to"]


def test_suggest_response_structure(client: TestClient) -> None:
    response = client.post(
        "/suggest",
        json={"rsc_question": "Emergency exits remain accessible during all shifts."},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "rsc_question",
        "mapped_to",
        "confidence",
        "rule",
        "source_candidates",
    }


def test_suggest_batch(client: TestClient) -> None:
    questions = [
        "The facility has a business license for legal operation.",
        "Emergency exits remain accessible during all shifts.",
    ]

    response = client.post("/suggest-batch", json={"rsc_questions": questions})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["results"]) == len(questions)


def test_suggest_batch_preserves_order(client: TestClient) -> None:
    questions = [
        "Emergency exits remain accessible during all shifts.",
        "The facility has a business license for legal operation.",
    ]

    response = client.post("/suggest-batch", json={"rsc_questions": questions})

    assert response.status_code == 200
    assert [result["rsc_question"] for result in response.json()["results"]] == questions


def test_suggest_handles_empty_question(client: TestClient) -> None:
    response = client.post("/suggest", json={"rsc_question": "   "})

    assert response.status_code == 400
    assert "rsc_question" in response.json()["detail"]


def test_api_error_handling(client: TestClient) -> None:
    response = client.post("/suggest", json={})

    assert response.status_code == 400
    assert response.json()["detail"]
