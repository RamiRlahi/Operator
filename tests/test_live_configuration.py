from unittest.mock import Mock

import pytest

from agent.llm import OpenAILLMClient
from main import run_interactive


def test_missing_bloomi_configuration_stops_before_creating_a_client(monkeypatch):
    for name in ("BLOOMI_API_KEY", "BLOOMI_BASE_URL", "BLOOMI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    constructor = Mock(side_effect=AssertionError("Unexpected API client"))
    monkeypatch.setattr("main.OpenAILLMClient", constructor)

    with pytest.raises(SystemExit, match="--live requires"):
        run_interactive("TKT-101", use_live_api=True)

    constructor.assert_not_called()


def test_provider_limits_and_rates_with_fake_transport(monkeypatch):
    sdk = Mock()
    request = sdk.return_value.chat.completions.create
    request.return_value.choices = [Mock()]
    request.return_value.choices[0].message.content = "Final Answer: Done."
    request.return_value.usage.prompt_tokens = 100
    request.return_value.usage.completion_tokens = 20
    monkeypatch.setattr("openai.OpenAI", sdk)

    client = OpenAILLMClient(api_key="fake", base_url="https://example.invalid/v1",
                             model="test-model", input_rate=1, output_rate=5)
    sdk.assert_called_once_with(api_key="fake", base_url="https://example.invalid/v1",
                                max_retries=0, timeout=30.0)
    request.assert_not_called()
    result = client.complete([{"role": "user", "content": "Test"}])
    assert result == ("Final Answer: Done.", 100, 20, 0.0002)
    assert request.call_args.kwargs["max_tokens"] == 500
