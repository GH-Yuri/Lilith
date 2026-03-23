from __future__ import annotations

import json
import logging
import time

from openai import OpenAI

from src.config import AIConfig

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5


class AIClient:
    """OpenAI-compatible client that works with GPT, Grok, Claude, etc."""

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def analyze(self, system_prompt: str, user_prompt: str) -> dict:
        """Send prompts to the AI model and return parsed JSON response."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.config.temperature,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                usage = response.usage
                logger.info(
                    "AI response | model=%s | tokens: prompt=%d completion=%d total=%d",
                    self.config.model,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                )

                return self._parse_response(content)

            except json.JSONDecodeError:
                logger.error(
                    "Failed to parse AI response as JSON (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, content,
                )
                if attempt == MAX_RETRIES:
                    return self._fallback_response("JSON parse error")

            except Exception as e:
                logger.error(
                    "AI API error (attempt %d/%d): %s", attempt, MAX_RETRIES, e
                )
                if attempt == MAX_RETRIES:
                    return self._fallback_response(str(e))
                time.sleep(RETRY_DELAY * attempt)

        return self._fallback_response("Max retries exceeded")

    def _parse_response(self, content: str) -> dict:
        parsed = json.loads(content)

        if "actions" not in parsed:
            parsed["actions"] = []
        if "notes" not in parsed:
            parsed["notes"] = ""
        if "market_assessment" not in parsed:
            parsed["market_assessment"] = "neutral"

        return parsed

    @staticmethod
    def _fallback_response(error: str) -> dict:
        return {
            "actions": [{"type": "HOLD", "reasoning": f"AI error: {error}"}],
            "notes": "",
            "market_assessment": "neutral",
        }
