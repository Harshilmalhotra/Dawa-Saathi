"""Read prescription images through Groq's OpenAI-compatible vision API."""
import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
import time
from typing import TypeVar

import httpx
from PIL import Image as PILImage
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.schemas import PrescriptionExtraction, StripExtraction

T = TypeVar("T", bound=BaseModel)

PRESCRIPTION_INSTRUCTION = """Transcribe visible prescription details only. Never diagnose, advise, infer, or guess. Return compact JSON only; no reasoning, explanation, summary, or markdown. Include only medicines with drug_name, strength, frequency_code, as_needed, food_timing, duration_days, each field's confidence, and uncertain_fields. Unclear values must be null with confidence 0 and listed in uncertain_fields. Do not include source_text, notes, language, legibility, or repeated details. Convert OD/BD/TDS/QID/HS and AC/PC only when clearly written. SOS means as_needed=true and frequency_code=null.
Example: {"medicines":[{"drug_name":null,"drug_name_conf":0,"strength":null,"strength_conf":0,"frequency_code":null,"frequency_conf":0,"as_needed":false,"food_timing":null,"food_timing_conf":0,"duration_days":null,"duration_conf":0,"uncertain_fields":["drug_name","frequency_code"]}]}"""

STRIP_INSTRUCTION = "Transcribe only the printed medicine name and strength visible on this strip. Never infer or advise. Return concise JSON only with printed_drug_name, printed_drug_name_conf, printed_strength, printed_strength_conf. Unclear values must be null with confidence 0."


class GroqAPIError(RuntimeError):
    """A safe provider error suitable for backend logs (never includes request data)."""


MAX_429_RETRIES = 2
MAX_RETRY_DELAY_SECONDS = 30.0
INITIAL_MAX_COMPLETION_TOKENS = 512
LONG_PRESCRIPTION_MAX_COMPLETION_TOKENS = 1024


def _image_data_url(path: str) -> str:
    with PILImage.open(path) as image:
        image.thumbnail((1600, 1600))
        import io

        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=88)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _message_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(part.get("text", "") for part in value if isinstance(part, dict))
    raise ValueError("Groq returned no text content")


def _provider_error(response: httpx.Response) -> GroqAPIError:
    message = "provider rejected the request"
    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            message = error["message"][:300]
    except ValueError:
        pass
    return GroqAPIError(f"Groq returned HTTP {response.status_code}: {message}")


def _retry_delay(response: httpx.Response) -> float | None:
    """Read Groq's server retry delay; return None when none is supplied."""
    raw = response.headers.get("retry-after")
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(raw)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass

    # Groq documents this reset header in duration form (for example, "7.66s").
    raw = response.headers.get("x-ratelimit-reset-tokens")
    if raw:
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)?\s*", raw, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = (match.group(2) or "s").lower()
            return value / 1000 if unit == "ms" else value * {"s": 1, "m": 60, "h": 3600}.get(unit, 1)

    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        metadata = error.get("metadata", {}) if isinstance(error, dict) else {}
        value = metadata.get("retry_after") if isinstance(metadata, dict) else None
        if value is not None:
            return max(0.0, float(value))
    except (ValueError, TypeError):
        pass
    return None


def _request(paths: list[str], instruction: str, schema: type[T]) -> T:
    if not settings.groq_api_key:
        raise RuntimeError("Groq is not configured. Set GROQ_API_KEY in the repository-root .env.")
    content: list[dict[str, object]] = [{"type": "text", "text": instruction}]
    content.extend({"type": "image_url", "image_url": {"url": _image_data_url(path)}} for path in paths)
    headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
    endpoint = f"{settings.groq_base_url.rstrip('/')}/chat/completions"
    for token_limit in (INITIAL_MAX_COMPLETION_TOKENS, LONG_PRESCRIPTION_MAX_COMPLETION_TOKENS):
        retry_count = 0
        while True:
            response = httpx.post(endpoint, headers=headers, json={
                "model": settings.groq_model,
                "messages": [
                    {"role": "system", "content": "Transcribe visible medical writing only. Never guess or give advice."},
                    {"role": "user", "content": content},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "max_completion_tokens": token_limit,
            }, timeout=90)
            if response.status_code == 429:
                delay = _retry_delay(response)
                if retry_count >= MAX_429_RETRIES or delay is None or delay > MAX_RETRY_DELAY_SECONDS:
                    suffix = f"; server requested {delay:.2f}s before retry" if delay is not None else "; no retry delay was provided"
                    raise GroqAPIError(f"Groq returned HTTP 429{suffix}")
                retry_count += 1
                time.sleep(delay)
                continue
            if response.is_error:
                raise _provider_error(response)
            payload = response.json()
            choice = payload["choices"][0]
            if choice.get("finish_reason") == "length":
                if token_limit == INITIAL_MAX_COMPLETION_TOKENS:
                    break
                raise ValueError("Groq JSON remained truncated at the larger completion token limit")
            try:
                text = _message_text(choice["message"]["content"])
                return schema.model_validate(json.loads(text))
            except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
                raise ValueError("Groq response was incomplete or did not match the extraction schema") from exc
            break
    raise ValueError("Groq response remained truncated at the completion token limit")


def extract_prescription(paths: list[str]) -> PrescriptionExtraction:
    return _request(paths, PRESCRIPTION_INSTRUCTION, PrescriptionExtraction)


def extract_strip(path: str) -> StripExtraction:
    return _request([path], STRIP_INSTRUCTION, StripExtraction)
