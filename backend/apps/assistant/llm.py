"""Thin wrapper around the Claude API (official `anthropic` SDK).

Every call returns validated JSON via structured outputs. Untrusted text (news) is only ever
sent from the explanation pipeline, which passes no tools - see PLAN.md §9.
"""
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)
_client = None


class LLMUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(settings.AI_FEATURES_ENABLED and settings.ANTHROPIC_API_KEY)


def client():
    global _client
    if not enabled():
        raise LLMUnavailable("AI features are disabled or ANTHROPIC_API_KEY is not set.")
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=2,
                                      timeout=60)
    return _client


def check_quota(user) -> None:
    """Per-user daily AI request budget (cost guardrail)."""
    key = f"ai_quota:{user.pk}:{timezone.now().date().isoformat()}"
    used = cache.get_or_set(key, 0, timeout=86400)
    if used >= settings.AI_DAILY_REQUESTS_PER_USER:
        raise LLMUnavailable("Daily AI request limit reached. It resets tomorrow.")
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=86400)


def structured(system: str, user_content: str, schema: dict, effort: str = "low",
               max_tokens: int = 2000, history: list | None = None) -> dict:
    """One request, JSON out. The static system prompt is cached (it comes first)."""
    import anthropic

    messages = [*(history or []), {"role": "user", "content": user_content}]
    try:
        resp = client().messages.create(
            model=settings.LLM_MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_config={"effort": effort,
                           "format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.RateLimitError as e:
        raise LLMUnavailable("The AI service is busy. Try again in a moment.") from e
    except anthropic.APIConnectionError as e:
        raise LLMUnavailable("Couldn't reach the AI service.") from e
    except anthropic.AuthenticationError as e:
        raise LLMUnavailable("The AI API key is invalid.") from e
    except anthropic.APIStatusError as e:
        log.warning("Claude API error %s: %s", e.status_code, e.message)
        raise LLMUnavailable("The AI service returned an error.") from e
    if resp.stop_reason == "refusal":
        raise LLMUnavailable("The AI declined this request.")
    if resp.stop_reason == "max_tokens":
        raise LLMUnavailable("The AI response was cut off.")
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        raise LLMUnavailable("Empty AI response.")
    log.info("claude %s in=%s out=%s cache_read=%s", settings.LLM_MODEL,
             resp.usage.input_tokens, resp.usage.output_tokens,
             getattr(resp.usage, "cache_read_input_tokens", None))
    return json.loads(text)
