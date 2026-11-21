"""CLI seed entrypoint: `python3 -m datacheck.seed`.

Seeds and exits — never starts the HTTP server.
"""

from __future__ import annotations

import logging
import sys

from .runner import seed_all


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    summary = seed_all()
    print(
        "Seed complete: "
        f"{summary['datasets']} datasets, "
        f"{summary['runs_total']} validation runs, "
        f"{summary['users']} users "
        f"({summary['runs_created']} runs created this pass)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
