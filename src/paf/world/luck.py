"""Keyed luck: every draw is named by what it is about, so every design meets the same world."""

from __future__ import annotations

import hashlib
import struct
from typing import Any


def uniform(seed: int, *key: object) -> float:
    """A uniform number in [0, 1) that depends only on the seed and the key."""
    h = hashlib.blake2b(digest_size=8, key=struct.pack("<q", seed))
    h.update("|".join(str(k) for k in key).encode())
    return (int.from_bytes(h.digest(), "little") >> 11) / float(1 << 53)


def choice(seed: int, items: list[Any], *key: object) -> Any:
    return items[int(uniform(seed, *key) * len(items))]


def randint(seed: int, lo: int, hi: int, *key: object) -> int:
    """An integer in [lo, hi]."""
    return lo + int(uniform(seed, *key) * (hi - lo + 1))


def normal(seed: int, *key: object) -> float:
    import math

    u1 = max(uniform(seed, *key, "n1"), 1e-12)
    u2 = uniform(seed, *key, "n2")
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2 * math.pi * u2)
