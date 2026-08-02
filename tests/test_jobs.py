from unittest.mock import Mock, patch

from kgeo.jobs import ollama_chat_job


def test_ollama_job_disables_thinking_and_returns_business_result() -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"message": {"content": '{"answer":"ok"}'}}
    with patch("kgeo.jobs.requests.post", return_value=response) as post:
        result = ollama_chat_job(
            [{"role": "user", "content": "本文"}],
            model="gemma4:12b-it-qat",
        )
    payload = post.call_args.kwargs["json"]
    assert payload["think"] is False
    assert payload["stream"] is False
    assert result["ok"] is True
    assert result["completion_scope"] == "business_result"
    assert result["ollama_host"] == "192.168.0.14"


def test_ollama_job_rejects_empty_messages() -> None:
    try:
        ollama_chat_job([])
    except RuntimeError as exc:
        assert str(exc) == "messages are required"
    else:
        raise AssertionError("empty messages must fail")
