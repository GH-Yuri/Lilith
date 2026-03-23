from __future__ import annotations

import json
import logging
import time

from src.config import AIConfig

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5


def _is_anthropic(config: AIConfig) -> bool:
    return "anthropic" in config.base_url


class AIClient:
    """Multi-provider AI client: OpenAI-compatible (GPT, Grok) + Anthropic (Claude)."""

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self._is_claude = _is_anthropic(config)

        if self._is_claude:
            import anthropic
            self._anthropic = anthropic.Anthropic(api_key=config.api_key)
        else:
            from openai import OpenAI
            self._openai = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def analyze(self, system_prompt: str, user_prompt: str) -> dict:
        """Send prompts to the AI model and return parsed JSON response."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self._is_claude:
                    content, prompt_tokens, completion_tokens = self._call_anthropic(
                        system_prompt, user_prompt
                    )
                else:
                    content, prompt_tokens, completion_tokens = self._call_openai(
                        system_prompt, user_prompt
                    )

                logger.info(
                    "AI response | model=%s | tokens: prompt=%d completion=%d total=%d",
                    self.config.model,
                    prompt_tokens,
                    completion_tokens,
                    prompt_tokens + completion_tokens,
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

    def _call_openai(
        self, system_prompt: str, user_prompt: str
    ) -> tuple[str, int, int]:
        response = self._openai.chat.completions.create(
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
        return content, usage.prompt_tokens, usage.completion_tokens

    def _call_anthropic(
        self, system_prompt: str, user_prompt: str
    ) -> tuple[str, int, int]:
        json_instruction = (
            "\n\nYou MUST respond with ONLY valid JSON, no other text. "
            "No markdown code fences, no explanations outside the JSON."
        )
        response = self._anthropic.messages.create(
            model=self.config.model,
            max_tokens=1024,
            system=system_prompt + json_instruction,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.config.temperature,
        )
        content = response.content[0].text
        return content, response.usage.input_tokens, response.usage.output_tokens

    def _parse_response(self, content: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        parsed = json.loads(cleaned)

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
