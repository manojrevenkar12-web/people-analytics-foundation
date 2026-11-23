"""Generated files keep ten significant digits, so a rerun on another machine diffs clean."""

from typing import Any


def tidy(obj: Any) -> Any:
    if isinstance(obj, float):
        return float(f"{obj:.10g}")
    if isinstance(obj, dict):
        return {k: tidy(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [tidy(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, str | bytes):
        return tidy(obj.item())
    return obj
