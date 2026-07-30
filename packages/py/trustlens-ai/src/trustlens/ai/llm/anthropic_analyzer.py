"""Claude adapter for listing analysis."""

from __future__ import annotations

import time

from trustlens.ai.llm.base import parse_analysis_json
from trustlens.ai.llm.prompts.listing_analysis_v1 import build_messages
from trustlens.core.domain.errors import ExternalServiceError
from trustlens.core.domain.ports.ai import ListingAnalysisResult
from trustlens.shared.logging import get_logger

log = get_logger(__name__)


class AnthropicAnalyzer:
    """Implements `LlmAnalyzer` using the Claude API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: int = 30,
        max_retries: int = 3,
        max_output_tokens: int = 2048,
        prompt_version: str = "v1",
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._prompt_version = prompt_version

        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    async def analyze_listing(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        currency: str | None,
        category: str | None,
    ) -> ListingAnalysisResult:
        system, user = build_messages(
            title=title,
            description=description,
            price=price,
            currency=currency,
            category=category,
        )
        started = time.monotonic()

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            # Raised as ExternalServiceError so the job retries and the signal
            # ends up UNAVAILABLE rather than FAIL - our outage must never
            # cost a seller points.
            log.warning("llm_analysis_failed", provider="anthropic", error=str(exc))
            raise ExternalServiceError("anthropic", str(exc)) from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        parsed = parse_analysis_json(text)

        return ListingAnalysisResult(
            risk_score=parsed["risk_score"],
            confidence=parsed["confidence"],
            labels=tuple(parsed["labels"]),
            findings=parsed["findings"],
            summary=parsed["summary"],
            provider="anthropic",
            model_name=self._model,
            model_version=response.model,
            prompt_version=self._prompt_version,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            raw={"stop_reason": response.stop_reason},
        )


__all__ = ["AnthropicAnalyzer"]
