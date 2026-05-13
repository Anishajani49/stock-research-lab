"""Minimal Ollama local-API client."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

log = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT

    def health(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as c:
                r = c.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=6))
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = True,
        temperature: float = 0.2,
    ) -> str:
        """Call Ollama /api/generate and return raw text (or stringified JSON)."""
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(f"{self.base_url}/api/generate", json=payload)
                r.raise_for_status()
                data = r.json()
                return data.get("response", "")
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama HTTP error: {e!s}") from e

    def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Generate and parse JSON. Retry on malformed output."""
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                raw = self.generate(
                    prompt=prompt if attempt == 0 else (
                        prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No prose."
                    ),
                    system=system,
                    json_mode=True,
                    temperature=temperature,
                )
                return json.loads(raw)
            except json.JSONDecodeError as e:
                last_err = e
                log.warning("LLM returned malformed JSON (attempt %d): %s", attempt + 1, e)
            except OllamaError as e:
                last_err = e
                log.warning("Ollama error (attempt %d): %s", attempt + 1, e)
        raise OllamaError(f"Failed to obtain valid JSON after {max_retries} attempts: {last_err}")
