#!/usr/bin/env python3
"""Smoke-check the AMS read API and summarize returned data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_ENDPOINTS = (
    ("health", "/health", {}),
    ("asset_summary", "/v1/assets/summary", {}),
    ("current_assets", "/v1/assets/current", {}),
    ("period_return", "/v1/returns/period", {"days": "{days}"}),
    ("portfolio_timeseries", "/v1/timeseries/portfolio", {"days": "{days}"}),
    ("platform_timeseries", "/v1/timeseries/platforms", {"days": "{days}"}),
    ("daily_metrics", "/v1/metrics/daily", {"days": "{days}", "limit": "{limit}"}),
    ("transactions", "/v1/transactions", {"days": "{days}", "limit": "{limit}"}),
    ("mdd", "/v1/risk/mdd", {"days": "{days}"}),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call AMS read API endpoints and verify JSON responses."
    )
    parser.add_argument(
        "--target",
        default="local",
        help="Named target from config JSON. Defaults to local.",
    )
    parser.add_argument(
        "--base-url",
        help="Explicit API base URL. Overrides --target and config files.",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Call api.main:app directly with FastAPI TestClient instead of HTTP.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config.json",
        help="Path to local config JSON. Defaults to .agent-workbench/config.json.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Lookback window for period, timeseries, metrics, transactions, and MDD.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum rows for list endpoints that support limit.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--require-data",
        action="store_true",
        help="Fail if all collection endpoints return empty lists and summary total is zero.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a text summary.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="With --json, print compact endpoint summaries instead of full payloads.",
    )
    parser.add_argument(
        "--mdd-without-days",
        action="store_true",
        help="Call /v1/risk/mdd without a days query parameter.",
    )
    return parser.parse_args()


def load_targets(config_path: Path) -> dict[str, str]:
    if config_path.exists():
        with config_path.open(encoding="utf-8") as file:
            return json.load(file).get("api_targets", {})

    example_path = config_path.with_name("config.example.json")
    if example_path.exists():
        with example_path.open(encoding="utf-8") as file:
            return json.load(file).get("api_targets", {})

    return {}


def resolve_base_url(args: argparse.Namespace) -> tuple[str, str]:
    if args.base_url:
        return args.base_url.rstrip("/"), "explicit --base-url"

    targets = load_targets(args.config)
    if args.target not in targets:
        available = ", ".join(sorted(targets)) or "none"
        raise SystemExit(
            f"Unknown API target '{args.target}'. Available targets: {available}"
        )
    return targets[args.target].rstrip("/"), f"target '{args.target}'"


def build_url(base_url: str, path: str, params: dict[str, str]) -> str:
    if not params:
        return f"{base_url}{path}"
    return f"{base_url}{path}?{urlencode(params)}"


def fetch_json(url: str, timeout: float) -> Any:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc


def fetch_in_process(path: str, params: dict[str, str]) -> Any:
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()


def collection_count(payload: Any) -> int | None:
    if isinstance(payload, list):
        return len(payload)
    return None


def has_any_data(results: list[dict[str, Any]]) -> bool:
    for result in results:
        payload = result["payload"]
        if isinstance(payload, list) and payload:
            return True
        if result["name"] == "asset_summary" and payload.get("total_krw", 0) != 0:
            return True
    return False


def compact_payload(name: str, payload: Any) -> Any:
    """Keep reusable API checks readable when large list payloads are returned."""
    if name == "current_assets" and isinstance(payload, list):
        by_platform: dict[str, float] = {}
        by_category: dict[str, float] = {}
        for asset in payload:
            platform = asset.get("platform") or "미분류"
            category = asset.get("category") or "미분류"
            amount = float(asset.get("eval_amount_krw") or 0)
            by_platform[platform] = by_platform.get(platform, 0) + amount
            by_category[category] = by_category.get(category, 0) + amount
        return {
            "count": len(payload),
            "by_platform": by_platform,
            "by_category": by_category,
        }

    if name == "platform_timeseries" and isinstance(payload, list):
        by_date: dict[str, dict[str, float]] = {}
        for row in payload:
            raw_date = row.get("date") or row.get("snapshot_date") or row.get("created_at")
            date = raw_date[:10] if isinstance(raw_date, str) else str(raw_date)
            platform = row.get("platform") or "미분류"
            value = (
                row.get("total_krw")
                or row.get("amount_krw")
                or row.get("value_krw")
                or 0
            )
            by_date.setdefault(date, {})[platform] = float(value)
        return {"count": len(payload), "by_date": by_date}

    if isinstance(payload, list):
        return {"count": len(payload), "items": payload}

    return payload


def compact_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted = []
    for result in results:
        compacted.append(
            {
                "name": result["name"],
                "url": result["url"],
                "ok": result["ok"],
                "count": result["count"],
                "payload": compact_payload(result["name"], result["payload"]),
            }
        )
    return compacted


def main() -> int:
    args = parse_args()
    if args.in_process:
        base_url, source = "in-process://api.main:app", "in-process api.main:app"
    else:
        base_url, source = resolve_base_url(args)
    substitutions = {"days": str(args.days), "limit": str(args.limit)}

    results = []
    failures = []
    for name, path, raw_params in DEFAULT_ENDPOINTS:
        if name == "mdd" and args.mdd_without_days:
            raw_params = {}
        params = {
            key: value.format(**substitutions) for key, value in raw_params.items()
        }
        url = build_url(base_url, path, params)
        try:
            if args.in_process:
                payload = fetch_in_process(path, params)
            else:
                payload = fetch_json(url, args.timeout)
            results.append(
                {
                    "name": name,
                    "url": url,
                    "ok": True,
                    "count": collection_count(payload),
                    "payload": payload,
                }
            )
        except Exception as exc:
            failures.append({"name": name, "url": url, "ok": False, "error": str(exc)})

    if args.require_data and not has_any_data(results):
        failures.append(
            {
                "name": "require_data",
                "url": base_url,
                "ok": False,
                "error": "No collection rows returned and asset summary total is zero.",
            }
        )

    report = {
        "ok": not failures,
        "target": source,
        "base_url": base_url,
        "results": compact_results(results) if args.compact else results,
        "failures": failures,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"AMS API smoke check target: {source} ({base_url})")
        for result in results:
            count = result["count"]
            suffix = f" count={count}" if count is not None else ""
            print(f"OK {result['name']}: {result['url']}{suffix}")
        for failure in failures:
            print(f"FAIL {failure['name']}: {failure['error']}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
