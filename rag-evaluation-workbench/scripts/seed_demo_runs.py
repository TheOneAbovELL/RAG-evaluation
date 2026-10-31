"""Create the five offline example runs used in the documentation (no network, no API key).

    uv run python scripts/seed_demo_runs.py
    uv run python scripts/seed_demo_runs.py --pages docs/project-book/tools/screenshot_pages.json

With ``--pages`` the script also writes the page list used by the screenshot tool. ``start.py`` creates the same
runs automatically the first time the app starts with an empty run store.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_workbench.demo import seed_demo_runs
from rag_workbench.services import open_context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pages", type=Path, help="write the screenshot page list here")
    args = parser.parse_args()
    runs = seed_demo_runs(open_context(console_logging=False))
    for key, run in runs.items():
        print(f"{key:<13} {run.id}  {run.status}")
    if args.pages:
        ids = {key: run.id for key, run in runs.items()}
        pages = [
            ["01-overview", "/"],
            ["02-new-evaluation", "/new-run"],
            ["03-results-summary", f"/results?run={ids['k3']}"],
            ["04-results-cases", f"/results?run={ids['k3']}&tab=cases"],
            ["05-case-detail", f"/results?run={ids['k3']}&tab=case&case=q10"],
            ["06-run-configuration", f"/results?run={ids['k3']}&tab=config"],
            ["07-failed-cases", f"/results?run={ids['failures']}&tab=cases"],
            ["08-compare", f"/compare?runs={ids['k1']},{ids['k3']},{ids['k5']}"],
            ["09-datasets", "/data"],
            ["10-settings", "/settings"],
            ["11-unanswerable", f"/results?run={ids['unanswerable']}&tab=cases"],
        ]
        args.pages.write_text(json.dumps(pages, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {args.pages}")


if __name__ == "__main__":
    main()
