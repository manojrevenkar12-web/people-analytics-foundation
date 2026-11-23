"""Real model adapters for the two pilots: Claude (Messages API) and any OpenAI-compatible endpoint.

Both ask for one JSON object and parse it strictly; anything else counts as low confidence, so code sends it to a
person. The prompts carry the question or the comment and the allowed answers, never names or worker ids.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

ANSWER_PROMPT = (
    "You answer employees' questions to the People team using only these policy passages.\n{passages}\n"
    'Reply with JSON only: {{"passage": "<id>", "quote": "<words copied from that passage>", '
    '"confidence": <0-1>}}.\n'
    "Question: {text}"
)
EXIT_PROMPT = (
    "Code the main reason this person gives for leaving. Themes: {themes}.\n"
    'Reply with JSON only: {{"theme": "<theme>", "quote": "<sentence copied from the comment>", '
    '"confidence": <0-1>}}.\n'
    "Comment: {text}"
)


def parse(raw: str, keys: tuple[str, ...]) -> dict:
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        obj = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"confidence": 0.0}
    if not isinstance(obj, dict) or any(k not in obj for k in keys):
        return {"confidence": 0.0}
    try:
        obj["confidence"] = float(obj["confidence"])
    except (TypeError, ValueError):
        obj["confidence"] = 0.0
    return obj


@dataclass
class ClaudeReader:
    api_key: str
    model: str = "claude-sonnet-5-5"
    url: str = "https://api.anthropic.com/v1/messages"
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=30))

    def _ask(self, prompt: str) -> str:
        r = self.client.post(
            self.url,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={"model": self.model, "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))

    def answer(self, ticket_id: str, text: str, passages: dict[str, str]) -> dict:
        ps = "\n".join(f"{k}: {v}" for k, v in passages.items())
        return parse(self._ask(ANSWER_PROMPT.format(passages=ps, text=text)), ("passage", "quote", "confidence"))

    def code_exit(self, response_id: str, text: str, themes: list[str]) -> dict:
        return parse(
            self._ask(EXIT_PROMPT.format(themes=", ".join(themes), text=text)), ("theme", "quote", "confidence")
        )


@dataclass
class OpenAICompatibleReader:
    base_url: str
    api_key: str
    model: str
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=30))

    def _ask(self, prompt: str) -> str:
        r = self.client.post(
            self.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
        )
        r.raise_for_status()
        return str(r.json()["choices"][0]["message"]["content"])

    def answer(self, ticket_id: str, text: str, passages: dict[str, str]) -> dict:
        ps = "\n".join(f"{k}: {v}" for k, v in passages.items())
        return parse(self._ask(ANSWER_PROMPT.format(passages=ps, text=text)), ("passage", "quote", "confidence"))

    def code_exit(self, response_id: str, text: str, themes: list[str]) -> dict:
        return parse(
            self._ask(EXIT_PROMPT.format(themes=", ".join(themes), text=text)), ("theme", "quote", "confidence")
        )
