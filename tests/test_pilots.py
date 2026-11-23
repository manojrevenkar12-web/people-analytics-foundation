"""The assistant's and the exit coder's checks, assignment and the effect estimate."""

import httpx
import numpy as np

from paf.platform import pilots, readers


class Scripted:
    def __init__(self, answer: dict | None = None, theme: dict | None = None) -> None:
        self.a, self.t, self.calls = answer or {}, theme or {}, 0

    def answer(self, ticket_id: str, text: str, passages: dict[str, str]) -> dict:
        self.calls += 1
        return self.a

    def code_exit(self, response_id: str, text: str, themes: list[str]) -> dict:
        self.calls += 1
        return self.t


def test_a_sensitive_question_never_reaches_the_model(cfg) -> None:  # type: ignore[no-untyped-def]
    r = Scripted({"passage": "P-VAC", "quote": "27 vacation days", "confidence": 0.99})
    d = pilots.assistant_decision(
        {"ticket_id": "T", "text": "I have a serious conflict with my manager."}, r, cfg, pilots.Guard()
    )
    assert d["route"] == "person" and r.calls == 0


def test_answers_go_out_only_when_every_check_passes(cfg) -> None:  # type: ignore[no-untyped-def]
    q = {"ticket_id": "T", "text": "How many vacation days do I have per year?"}
    good = {"passage": "P-VAC", "quote": "27 vacation days a year", "confidence": 0.95}
    assert pilots.assistant_decision(q, Scripted(good), cfg, pilots.Guard())["route"] == "sent"
    for bad in (
        {**good, "passage": "P-XXX"},
        {**good, "quote": "unlimited leave"},
        {**good, "confidence": 0.4},
        {"passage": "P-PEN", "quote": "The company adds 20 percent", "confidence": 0.95},
    ):
        assert pilots.assistant_decision(q, Scripted(bad), cfg, pilots.Guard())["route"] == "person"


def test_exit_codes_need_a_quote_that_names_the_theme_and_is_not_praise(cfg) -> None:  # type: ignore[no-untyped-def]
    resp = {
        "response_id": "S",
        "text": "My manager was great and supportive. I could not make the numbers work on my current pay.",
    }
    ok = {"theme": "pay", "quote": "I could not make the numbers work on my current pay.", "confidence": 0.9}
    assert pilots.code_exit(resp, Scripted(theme=ok), cfg, pilots.Guard())["by"] == "model"
    praise = {"theme": "manager", "quote": "My manager was great and supportive.", "confidence": 0.9}
    invented = {"theme": "workload", "quote": "the overtime was too much", "confidence": 0.9}
    off = {"theme": "culture", "quote": "I could not make the numbers work on my current pay.", "confidence": 0.9}
    for bad in (praise, invented, off, {"theme": "astrology", "quote": ok["quote"], "confidence": 0.9}):
        assert pilots.code_exit(resp, Scripted(theme=bad), cfg, pilots.Guard())["by"] == "person"


def test_assignment_is_stable_and_about_half() -> None:
    ids = [f"W-{i:05d}" for i in range(2000)]
    arms = [pilots.treated(i, 0.5) for i in ids]
    assert arms == [pilots.treated(i, 0.5) for i in ids]
    assert 0.45 < np.mean(arms) < 0.55


def test_the_interval_covers_a_known_difference() -> None:
    rng = np.random.default_rng(1)
    a, b = rng.normal(3.0, 1.0, 400), rng.normal(5.0, 1.0, 400)
    point, lo, hi = pilots.diff_ci(a, b, np.arange(400) % 80, np.arange(400) % 80)
    assert lo < -2.0 < hi and abs(point + 2.0) < 0.3


def test_real_adapters_parse_json_and_never_send_ids() -> None:
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.content.decode())
        if "anthropic" in str(req.url):
            return httpx.Response(
                200, json={"content": [{"type": "text", "text": '{"theme": "pay", "quote": "x", "confidence": 0.9}'}]}
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    c = readers.ClaudeReader("k", client=client)
    assert c.code_exit("S-0007", "The pay was low.", ["pay"])["theme"] == "pay"
    o = readers.OpenAICompatibleReader("https://llm.example", "k", "m", client=client)
    assert o.answer("T-00042", "When is payday?", {"P-PAY": "last working day"})["confidence"] == 0.0
    assert not any("S-0007" in s or "T-00042" in s for s in seen)
