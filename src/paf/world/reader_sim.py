"""The model as a part of the world: it reads what people wrote and makes the mistakes world.yml says it makes.

It knows the truth only to decide what mistake to make. Every mistake is keyed by what it is about, so every design
meets the same model.
"""

from __future__ import annotations

from paf.world import luck
from paf.world.systems import Keys
from paf.world.texts import PRAISE, QUESTIONS, REASONS


class SimReader:
    def __init__(self, keys: Keys, w: dict, world_name: str, seed: int) -> None:
        self.keys = keys
        self.r = w["reader"]
        self.seed = seed
        self.new_share = float(w[world_name].get("new_phrasing_share", 0.0))
        self.calls = 0

    def _is_new(self, text: str, pools: list[list[str]]) -> bool:
        return not any(text.startswith(s) or s in text for pool in pools for s in pool)

    def answer(self, ticket_id: str, text: str, passages: dict[str, str]) -> dict:
        self.calls += 1
        t = self.keys.ticket_truth[ticket_id]
        r = self.r["helpdesk"]
        u = luck.uniform(self.seed, "rd-hd", ticket_id)
        base = next(q for q in QUESTIONS if q[0] == t["category"])
        new = text not in base[1]
        ids = list(passages)
        if t["answer"] == "person":
            pid = luck.choice(self.seed, ids, "rd-hd-sens", ticket_id)  # answers anyway, from some passage
            return {"passage": pid, "quote": passages[pid][:40], "confidence": 0.8}
        wrong = r["wrong_passage"] * (2.0 if new else 1.0)
        if u < wrong:
            pid = luck.choice(self.seed, [p for p in ids if p != t["answer"]], "rd-hd-wrong", ticket_id)
            return {"passage": pid, "quote": passages[pid][:40], "confidence": 0.82}
        if u < wrong + r["invents_answer"]:
            return {"passage": t["answer"], "quote": "employees may take unlimited leave", "confidence": 0.85}
        if u < wrong + r["invents_answer"] + r["low_confidence"]:
            return {"passage": t["answer"], "quote": passages[t["answer"]][:40], "confidence": 0.5}
        return {"passage": t["answer"], "quote": passages[t["answer"]][:40], "confidence": 0.93}

    def code_exit(self, response_id: str, text: str, themes: list[str]) -> dict:
        self.calls += 1
        reason = self.keys.survey_truth[response_id]
        r = self.r["exit"]
        u = luck.uniform(self.seed, "rd-ex", response_id)
        new = not any(s in text for s in REASONS[reason][0])
        sentences = [s.strip() + "." for s in text.split(".") if s.strip()]
        reason_sentence = next(
            (s for s in sentences if any(s.startswith(x[:20]) for x in REASONS[reason][0] + REASONS[reason][1])),
            sentences[0],
        )
        praise = next(((th, s) for th, s in PRAISE.items() if s in text), None)
        subtle = r["misses_subtle"] * (2.5 if new else 1.0)
        if u < subtle:
            return {
                "theme": "culture" if reason != "culture" else "role_fit",
                "quote": sentences[-1],
                "confidence": 0.75,
            }
        u -= subtle
        if praise and u < r["takes_praise_as_reason"]:
            return {"theme": praise[0], "quote": praise[1], "confidence": 0.78}
        u -= r["takes_praise_as_reason"] if praise else 0.0
        if u < r["invents_theme"]:
            other = [t for t in themes if t != reason]
            return {
                "theme": luck.choice(self.seed, other, "rd-ex-inv", response_id),
                "quote": "the commute was impossible",
                "confidence": 0.8,
            }
        u -= r["invents_theme"]
        if u < r["low_confidence"]:
            return {"theme": reason, "quote": reason_sentence, "confidence": 0.55}
        return {"theme": reason, "quote": reason_sentence, "confidence": 0.9}
