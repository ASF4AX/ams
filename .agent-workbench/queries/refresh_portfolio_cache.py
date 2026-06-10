#!/usr/bin/env python3
"""Refresh the external portfolio cache snapshot from the AMS read API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from app.utils.portfolio_cache import build_portfolio_cache

from api_smoke_check import load_targets


DEFAULT_OUTPUT = REPO_ROOT / ".agent-bridge" / "portfolio_cache.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch AMS portfolio data and write portfolio_cache.json."
    )
    parser.add_argument("--target", default="local")
    parser.add_argument("--base-url")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination JSON file. Defaults to .agent-bridge/portfolio_cache.json.",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def resolve_base_url(args: argparse.Namespace) -> str:
    if args.base_url:
        return args.base_url.rstrip("/")

    targets = load_targets(args.config)
    if args.target not in targets:
        available = ", ".join(sorted(targets)) or "none"
        raise SystemExit(
            f"Unknown API target '{args.target}'. Available targets: {available}"
        )
    return targets[args.target].rstrip("/")


def fetch_json(base_url: str, path: str, params: dict[str, Any], timeout: float) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(f"{base_url}{path}{query}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    args = parse_args()
    base_url = resolve_base_url(args)

    summary = fetch_json(base_url, "/v1/assets/summary", {}, args.timeout)
    current_assets = fetch_json(base_url, "/v1/assets/current", {}, args.timeout)
    return_7d = fetch_json(base_url, "/v1/returns/period", {"days": 7}, args.timeout)
    return_30d = fetch_json(base_url, "/v1/returns/period", {"days": 30}, args.timeout)
    mdd_30d = fetch_json(base_url, "/v1/risk/mdd", {"days": 30}, args.timeout)

    payload = build_portfolio_cache(
        summary=summary,
        current_assets=current_assets,
        return_7d=return_7d,
        return_30d=return_30d,
        mdd_30d=mdd_30d,
        source=f"AMS API @ {base_url}",
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
