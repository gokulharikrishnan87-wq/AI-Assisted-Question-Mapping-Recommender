import builtins
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from mapper_copilot.providers.llm import BedrockLLM, LLMProvider, MockLLM


class NoCredentialsError(Exception):
    pass


class TestMockLLM:
    def test_llm_generate_returns_string(self):
        llm = MockLLM()
        response = llm.generate("Suggest mappings for item A")
        assert isinstance(response, str)

    def test_llm_generate_deterministic(self):
        llm = MockLLM()
        prompt = "Map RSC question to SLCP keys"
        assert llm.generate(prompt) == llm.generate(prompt)

    def test_llm_generate_deterministic_across_processes(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = "\n".join(
            [
                "import os",
                "import sys",
                "sys.path.insert(0, os.path.abspath('src'))",
                "from mapper_copilot.providers.llm import MockLLM",
                "print(MockLLM().generate('hello world'))",
            ]
        )

        response1 = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=repo_root,
            text=True,
        ).strip()
        response2 = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=repo_root,
            text=True,
        ).strip()

        assert response1 == response2

    def test_llm_generate_different_prompts_different_outputs(self):
        llm = MockLLM()
        assert llm.generate("first prompt") != llm.generate("second prompt")

    def test_llm_batch_generate(self):
        llm = MockLLM()
        prompts = ["one", "two", "three"]
        responses = llm.generate_batch(prompts)
        assert responses == [llm.generate(prompt) for prompt in prompts]

    def test_llm_mock_handles_empty_prompt(self):
        llm = MockLLM()
        response = llm.generate("")
        assert isinstance(response, str)
        assert response.startswith("Mock response for []:")


class TestBedrockLLM:
    def test_bedrock_instantiation(self):
        llm = BedrockLLM(model_id="anthropic.claude-v2")
        assert llm.model_id == "anthropic.claude-v2"

    def test_bedrock_generate_raises_on_missing_credentials(self, monkeypatch):
        class FailingClient:
            def invoke_model(self, **kwargs):
                raise NoCredentialsError()

        fake_boto3 = SimpleNamespace(client=lambda service_name: FailingClient())
        monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

        llm = BedrockLLM()

        with pytest.raises(RuntimeError, match="AWS credentials not configured"):
            llm.generate("hello")

    def test_bedrock_generate_wraps_credential_errors(self, monkeypatch):
        llm = BedrockLLM()

        class FailingClient:
            def invoke_model(self, **kwargs):
                raise Exception("ExpiredTokenException: token expired")

        monkeypatch.setattr(llm, "_get_client", lambda: FailingClient())

        with pytest.raises(RuntimeError, match="AWS credentials not configured"):
            llm.generate("hello")

    def test_bedrock_generate_wraps_other_errors(self, monkeypatch):
        llm = BedrockLLM()

        class FailingClient:
            def invoke_model(self, **kwargs):
                raise Exception("ValidationException: bad request")

        monkeypatch.setattr(llm, "_get_client", lambda: FailingClient())

        with pytest.raises(RuntimeError, match="Bedrock request failed"):
            llm.generate("hello")

    def test_bedrock_generate_sends_proper_json_headers(self, monkeypatch):
        llm = BedrockLLM(model_id="anthropic.claude-v2")
        captured = {}

        class SuccessfulClient:
            def invoke_model(self, **kwargs):
                captured.update(kwargs)
                return {"body": io.BytesIO(b'{"generation": "done"}')}

        monkeypatch.setattr(llm, "_get_client", lambda: SuccessfulClient())

        response = llm.generate("hello")

        assert response == "done"
        assert captured["modelId"] == "anthropic.claude-v2"
        assert json.loads(captured["body"]) == {"prompt": "hello"}
        assert captured["contentType"] == "application/json"
        assert captured["accept"] == "application/json"

    def test_bedrock_generate_batch(self, monkeypatch):
        llm = BedrockLLM()
        monkeypatch.setattr(llm, "generate", lambda prompt: prompt.upper())

        responses = llm.generate_batch(["a", "b", "c"])

        assert responses == ["A", "B", "C"]

    def test_bedrock_boto3_missing_error(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "boto3":
                raise ImportError("No module named 'boto3'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        llm = BedrockLLM()

        with pytest.raises(RuntimeError, match="boto3 not installed"):
            llm.generate("hello")

    def test_abstract_interface_enforcement(self):
        with pytest.raises(TypeError):
            LLMProvider()
