import json

import httpx
import pytest

from app.schemas import PrescriptionExtraction
from app.services import groq


def valid_result() -> dict:
    return {
        "medicines": [{
            "drug_name": "Example",
            "drug_name_conf": 0.9,
            "strength": None,
            "strength_conf": 0,
            "frequency_code": "1-0-1-0",
            "frequency_conf": 0.9,
            "as_needed": False,
            "food_timing": None,
            "food_timing_conf": 0,
            "duration_days": None,
            "duration_conf": 0,
            "uncertain_fields": ["strength", "food_timing", "duration_days"],
        }]
    }


def test_429_uses_server_retry_after_and_starts_at_512(monkeypatch):
    monkeypatch.setattr(groq.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(groq, "_image_data_url", lambda _: "data:image/jpeg;base64,AA==")
    delays = []
    monkeypatch.setattr(groq.time, "sleep", delays.append)
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, json={"error": {"message": "rate limited"}})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(valid_result())}}]})

    monkeypatch.setattr(groq.httpx, "post", fake_post)
    result = groq._request(["unused.jpg"], groq.PRESCRIPTION_INSTRUCTION, PrescriptionExtraction)

    assert len(result.medicines) == 1
    assert delays == [2.0]
    assert [call["json"]["max_completion_tokens"] for call in calls] == [512, 512]


def test_429_retry_count_is_bounded_and_no_delay_fails_fast(monkeypatch):
    monkeypatch.setattr(groq.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(groq, "_image_data_url", lambda _: "data:image/jpeg;base64,AA==")
    delays = []
    monkeypatch.setattr(groq.time, "sleep", delays.append)
    calls = []

    def retryable(*args, **kwargs):
        calls.append(kwargs)
        return httpx.Response(429, headers={"Retry-After": "1"}, json={"error": {"message": "rate limited"}})

    monkeypatch.setattr(groq.httpx, "post", retryable)
    with pytest.raises(groq.GroqAPIError, match="HTTP 429"):
        groq._request(["unused.jpg"], groq.PRESCRIPTION_INSTRUCTION, PrescriptionExtraction)
    assert len(calls) == 3
    assert delays == [1.0, 1.0]

    calls.clear()
    monkeypatch.setattr(groq.httpx, "post", lambda *args, **kwargs: calls.append(kwargs) or httpx.Response(429))
    with pytest.raises(groq.GroqAPIError, match="no retry delay"):
        groq._request(["unused.jpg"], groq.PRESCRIPTION_INSTRUCTION, PrescriptionExtraction)
    assert len(calls) == 1


def test_truncated_json_retries_once_with_larger_limit(monkeypatch):
    monkeypatch.setattr(groq.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(groq, "_image_data_url", lambda _: "data:image/jpeg;base64,AA==")
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{\"medicines\":["}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(valid_result())}}]})

    monkeypatch.setattr(groq.httpx, "post", fake_post)
    result = groq._request(["unused.jpg"], groq.PRESCRIPTION_INSTRUCTION, PrescriptionExtraction)
    assert result.medicines[0].drug_name == "Example"
    assert [call["json"]["max_completion_tokens"] for call in calls] == [512, 1024]


def test_truncated_json_at_larger_limit_fails_without_partial_result(monkeypatch):
    monkeypatch.setattr(groq.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(groq, "_image_data_url", lambda _: "data:image/jpeg;base64,AA==")
    calls = []

    def truncated(*args, **kwargs):
        calls.append(kwargs)
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{\"medicines\":["}}]})

    monkeypatch.setattr(groq.httpx, "post", truncated)
    with pytest.raises(ValueError, match="remained truncated"):
        groq._request(["unused.jpg"], groq.PRESCRIPTION_INSTRUCTION, PrescriptionExtraction)
    assert len(calls) == 2
