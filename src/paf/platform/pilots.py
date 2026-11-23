"""AI pilots for the People team, and how their effect is measured.

Helpdesk assistant: questions on sensitive topics go to a person before any model reads them. Otherwise the model
picks a policy passage, quotes it and says how sure it is; code sends the answer only if the passage exists, the
quote is in it, the question names the passage's topic and the confidence clears the bar. Everything else is held for
a person.

Exit-comment coding: the model names a theme from the taxonomy and quotes the sentence that says so; code keeps it
only if the theme is in the taxonomy, the quote is in the comment, the quote names the theme and is not praise, and
the confidence clears the bar. Everything else is coded by a person.

Measurement: requesters are split by a hash of their id into assistant and manual groups for the pilot months; the
effect is the difference between the groups with a bootstrap interval over requesters. A before/after comparison is
computed too, to show how far it can drift.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

import numpy as np


class Reader(Protocol):
    def answer(self, ticket_id: str, text: str, passages: dict[str, str]) -> dict: ...
    def code_exit(self, response_id: str, text: str, themes: list[str]) -> dict: ...


@dataclass
class Guard:
    sensitive_rule: bool = True
    checks: bool = True


def is_sensitive(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


def treated(requester: str, share: float) -> bool:
    h = int(hashlib.sha256(requester.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return h < share


def assistant_decision(ticket: dict, reader: Reader, cfg: dict, guard: Guard) -> dict:
    """What the assistant does with one ticket. Returns route ('sent' | 'person'), passage, model_read."""
    hd = cfg["helpdesk"]
    if guard.sensitive_rule and is_sensitive(ticket["text"], hd["sensitive_keywords"]):
        return {"route": "person", "passage": None, "model_read": False, "reason": "sensitive topic"}
    out = reader.answer(ticket["ticket_id"], ticket["text"], hd["passages"])
    pid = out.get("passage")
    if not guard.checks:
        return {"route": "sent", "passage": pid, "model_read": True, "reason": ""}
    if pid not in hd["passages"]:
        return {"route": "person", "passage": None, "model_read": True, "reason": "no such passage"}
    if not out.get("quote") or out["quote"] not in hd["passages"][pid]:
        return {"route": "person", "passage": None, "model_read": True, "reason": "quote not in passage"}
    if float(out.get("confidence", 0)) < float(hd["min_confidence"]):
        return {"route": "person", "passage": None, "model_read": True, "reason": "low confidence"}
    if not any(k in ticket["text"].lower() for k in hd["passage_topics"].get(pid, [])):
        return {"route": "person", "passage": None, "model_read": True, "reason": "passage off topic"}
    return {"route": "sent", "passage": pid, "model_read": True, "reason": ""}


def code_exit(resp: dict, reader: Reader, cfg: dict, guard: Guard) -> dict:
    ec = cfg["exit_coding"]
    out = reader.code_exit(resp["response_id"], resp["text"], list(ec["themes"]))
    theme = out.get("theme")
    if not guard.checks:
        return {"theme": theme, "by": "model"}
    if theme not in ec["themes"]:
        return {"theme": None, "by": "person", "reason": "theme not in taxonomy"}
    if not out.get("quote") or out["quote"] not in resp["text"]:
        return {"theme": None, "by": "person", "reason": "quote not in comment"}
    if float(out.get("confidence", 0)) < float(ec["min_confidence"]):
        return {"theme": None, "by": "person", "reason": "low confidence"}
    quote = out["quote"].lower()
    if not any(c in quote for c in ec["cues"].get(theme, [])):
        return {"theme": None, "by": "person", "reason": "quote does not name the theme"}
    if any(p in quote.split() or p in quote for p in ec["praise"]):
        return {"theme": None, "by": "person", "reason": "quote is praise"}
    return {"theme": theme, "by": "model"}


def diff_ci(
    a: np.ndarray, b: np.ndarray, ga: np.ndarray, gb: np.ndarray, n_boot: int = 1000
) -> tuple[float, float, float]:
    """Mean(a) - mean(b), with a bootstrap over clusters (requesters) within each group."""
    rng = np.random.default_rng(7)
    point = float(a.mean() - b.mean())
    ua, ub = np.unique(ga), np.unique(gb)
    ia = {g: np.flatnonzero(ga == g) for g in ua}
    ib = {g: np.flatnonzero(gb == g) for g in ub}
    boots = []
    for _ in range(n_boot):
        sa = np.concatenate([ia[g] for g in rng.choice(ua, len(ua))])
        sb = np.concatenate([ib[g] for g in rng.choice(ub, len(ub))])
        boots.append(a[sa].mean() - b[sb].mean())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)
