"""LLM provider implementations (mock and Bedrock)."""

from abc import ABC, abstractmethod
import hashlib
import json
from typing import List


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text response from a prompt."""
        pass

    @abstractmethod
    def generate_batch(self, prompts: List[str]) -> List[str]:
        """Generate responses for multiple prompts."""
        pass


class MockLLM(LLMProvider):
    """Deterministic offline LLM provider for tests and local development."""

    _WORD_BANK = (
        "alpha",
        "bravo",
        "charlie",
        "delta",
        "echo",
        "foxtrot",
        "golf",
        "hotel",
        "india",
        "juliet",
        "kilo",
        "lima",
        "mike",
        "november",
        "oscar",
        "papa",
    )

    def generate(self, prompt: str) -> str:
        """Generate a deterministic mock response for a prompt."""
        digest = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        snippet = prompt[:20]
        words = []
        for index in range(0, 12, 2):
            token = int(digest[index : index + 2], 16)
            words.append(self._WORD_BANK[token % len(self._WORD_BANK)])
        return f"Mock response for [{snippet}]: {' '.join(words)} ({digest[:8]})"

    def generate_batch(self, prompts: List[str]) -> List[str]:
        """Generate deterministic mock responses for multiple prompts."""
        return [self.generate(prompt) for prompt in prompts]


class BedrockLLM(LLMProvider):
    """AWS Bedrock LLM provider for production use."""

    def __init__(self, model_id: str = "anthropic.claude-v2"):
        """Initialize the Bedrock-backed LLM provider."""
        self.model_id = model_id
        self.client = None

    def _get_client(self):
        """Lazily initialize the boto3 Bedrock runtime client."""
        if self.client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError("boto3 not installed for Bedrock support") from exc
            self.client = boto3.client("bedrock-runtime")
        return self.client

    def generate(self, prompt: str) -> str:
        """Generate text with AWS Bedrock."""
        try:
            response = self._get_client().invoke_model(
                modelId=self.model_id,
                body=json.dumps({"prompt": prompt}),
                contentType="application/json",
                accept="application/json",
            )
            payload = self._parse_response(response)
            if "generation" in payload and isinstance(payload["generation"], str):
                return payload["generation"]
            completions = payload.get("completions")
            if isinstance(completions, list) and completions:
                first_completion = completions[0]
                if isinstance(first_completion, dict):
                    for key in ("data", "completion", "text", "generation"):
                        value = first_completion.get(key)
                        if isinstance(value, str):
                            return value
                if isinstance(first_completion, str):
                    return first_completion
            raise RuntimeError("Bedrock request failed: missing generation text in response")
        except RuntimeError:
            raise
        except Exception as exc:
            if self._is_credential_error(exc):
                raise RuntimeError(f"AWS credentials not configured: {exc}") from exc
            raise RuntimeError(f"Bedrock request failed: {exc}") from exc

    def generate_batch(self, prompts: List[str]) -> List[str]:
        """Generate text for multiple prompts."""
        return [self.generate(prompt) for prompt in prompts]

    def _parse_response(self, response: dict) -> dict:
        """Parse the JSON payload returned by Bedrock."""
        try:
            body = response["body"]
            if hasattr(body, "read"):
                body = body.read()
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            if not isinstance(body, str):
                raise TypeError("response body must be bytes or string")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise TypeError("response payload must be a JSON object")
            return payload
        except Exception as exc:
            raise RuntimeError(f"Bedrock request failed: {exc}") from exc

    @staticmethod
    def _is_credential_error(exc: Exception) -> bool:
        """Return True when an exception indicates missing AWS credentials or region."""
        details = f"{exc.__class__.__name__} {exc}".lower()
        return any(
            phrase in details
            for phrase in (
                "credential",
                "nocredentialserror",
                "partialcredentialserror",
                "region",
                "noregionerror",
                "expiredtoken",
                "accessdenied",
                "authorization",
                "security token",
            )
        )
