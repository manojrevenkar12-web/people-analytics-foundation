"""paf command line.

python -m paf.cli run dev        every design on the development seeds
python -m paf.cli run heldout    once, behind reports/heldout.lock
python -m paf.cli gate dev       exit 1 when a gate fails
python -m paf.cli report         REPORT.md, the README block, the console data and the Power BI files
"""

from __future__ import annotations

import argparse
import json
import sys

from paf.lab import report, study


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="paf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("world", choices=["dev", "heldout"])
    r.add_argument("--workers", type=int, default=2)
    g = sub.add_parser("gate")
    g.add_argument("world", choices=["dev", "heldout"])
    sub.add_parser("report")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        print("wrote", study.run_dev(a.workers) if a.world == "dev" else study.run_heldout(a.workers))
        return 0
    if a.cmd == "gate":
        data = json.loads((study.REPORTS / f"{a.world}.json").read_text())
        for x in data["gates"]:
            print(("PASS " if x["pass"] else "FAIL ") + f"{x['gate']}: {x['value']:.4g} {x['op']} {x['limit']}")
        return 0 if all(x["pass"] for x in data["gates"]) else 1
    report.write_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
