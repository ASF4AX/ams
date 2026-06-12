#!/usr/bin/env python3
"""Refresh the external portfolio cache snapshot from the AMS read API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
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
DEFAULT_JOBS_INDEX = REPO_ROOT / ".agent-bridge" / "JOBS.md"
DEFAULT_JOB_DETAIL = REPO_ROOT / ".agent-bridge" / "JOB-012_포트폴리오_캐시_JSON_생성.md"


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
    parser.add_argument(
        "--sync-job-records",
        action="store_true",
        help="Also update .agent-bridge JOB-012/JOBS.md with the latest snapshot values.",
    )
    parser.add_argument(
        "--jobs-index",
        type=Path,
        default=DEFAULT_JOBS_INDEX,
        help="Path to JOBS.md when --sync-job-records is used.",
    )
    parser.add_argument(
        "--job-detail",
        type=Path,
        default=DEFAULT_JOB_DETAIL,
        help="Path to JOB-012 detail file when --sync-job-records is used.",
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


def _featured_position(cache: dict[str, Any]) -> dict[str, Any] | None:
    positions = cache.get("positions", [])
    for position in positions:
        if position.get("return_pct") is not None:
            return position
    return positions[0] if positions else None


def _format_example_block(cache: dict[str, Any]) -> str:
    featured = _featured_position(cache) or {
        "ticker": None,
        "name": None,
        "platform": None,
        "asset_class": None,
        "shares": 0,
        "value_krw": 0,
        "weight_pct": None,
        "cost_basis_krw": None,
        "avg_price": None,
        "unrealized_pnl_krw": None,
        "return_pct": None,
    }
    summary = cache["summary"]
    returns = cache["returns"]
    mdd = cache["mdd"]
    by_platform = cache["by_platform"][1] if len(cache["by_platform"]) > 1 else cache["by_platform"][0]
    by_asset_class = cache["by_asset_class"][2] if len(cache["by_asset_class"]) > 2 else cache["by_asset_class"][0]
    return f"""   ```jsonc
   {{
     "as_of": "{cache['as_of']}",   // 조회 시각 ISO8601(타임존 포함)
     "source": "{cache['source']}",
     "base_currency": "KRW",
     "summary": {{
       "as_of_date": "{summary['as_of_date']}", "total_assets_krw": {summary['total_assets_krw']}, "item_count": {summary['item_count']},
       "total_cost_krw": {json.dumps(summary['total_cost_krw'], ensure_ascii=False)}, "total_unrealized_pnl_krw": {json.dumps(summary['total_unrealized_pnl_krw'], ensure_ascii=False)}, "total_return_pct": {json.dumps(summary['total_return_pct'], ensure_ascii=False)}
     }},
     "returns": {{ "d7_pct": {json.dumps(returns['d7_pct'], ensure_ascii=False)}, "d30_pct": {json.dumps(returns['d30_pct'], ensure_ascii=False)} }},
     "mdd": {{ "measured_30d_pct": {json.dumps(mdd['measured_30d_pct'], ensure_ascii=False)}, "api_raw_pct": null, "note": "{mdd['note']}" }},
     "by_platform":    [ {{ "platform": "{by_platform['platform']}", "value_krw": {by_platform['value_krw']} }} ],
     "by_asset_class": [ {{ "class": "{by_asset_class['class']}", "value_krw": {by_asset_class['value_krw']} }} ],
     "positions": [
       {{
         "ticker": {json.dumps(featured['ticker'], ensure_ascii=False)}, "name": {json.dumps(featured['name'], ensure_ascii=False)}, "platform": {json.dumps(featured['platform'], ensure_ascii=False)}, "asset_class": {json.dumps(featured['asset_class'], ensure_ascii=False)},
         "shares": {json.dumps(featured['shares'], ensure_ascii=False)}, "value_krw": {json.dumps(featured['value_krw'], ensure_ascii=False)}, "weight_pct": {json.dumps(featured['weight_pct'], ensure_ascii=False)},
         "cost_basis_krw": {json.dumps(featured['cost_basis_krw'], ensure_ascii=False)}, "avg_price": {json.dumps(featured['avg_price'], ensure_ascii=False)}, "unrealized_pnl_krw": {json.dumps(featured['unrealized_pnl_krw'], ensure_ascii=False)}, "return_pct": {json.dumps(featured['return_pct'], ensure_ascii=False)}
       }}
     ]
   }}
   ```"""


def sync_job_records(cache: dict[str, Any], jobs_index: Path, job_detail: Path) -> None:
    as_of_date = cache["summary"]["as_of_date"]
    total_assets = cache["summary"]["total_assets_krw"]
    item_count = cache["summary"]["item_count"]

    jobs_text = jobs_index.read_text(encoding="utf-8")
    jobs_footer = (
        f"*마지막 업데이트: {as_of_date} (JOB-012 반복 실행 — 최신 포트폴리오 캐시 갱신)*"
    )
    jobs_text = re.sub(r"\*마지막 업데이트:.*\*", jobs_footer, jobs_text)
    jobs_index.write_text(jobs_text, encoding="utf-8")

    detail_text = job_detail.read_text(encoding="utf-8")
    detail_text = re.sub(
        r"   ```jsonc\n.*?   ```",
        _format_example_block(cache),
        detail_text,
        count=1,
        flags=re.S,
    )
    detail_text = re.sub(
        r"\| 완료일 \| [0-9-]+ \|",
        f"| 완료일 | {as_of_date} |",
        detail_text,
        count=1,
    )
    detail_text = re.sub(
        r"현재 캐시 기준일은 .*?positions 항목 수는 [0-9]+개다\.",
        f"현재 캐시 기준일은 {as_of_date}, 총자산은 {total_assets:,} KRW, positions 항목 수는 {item_count}개다.",
        detail_text,
        count=1,
    )
    job_detail.write_text(detail_text, encoding="utf-8")


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
    if args.sync_job_records:
        sync_job_records(payload, args.jobs_index, args.job_detail)

    print(
        json.dumps(
            {
                "output": str(args.output),
                "as_of_date": payload["summary"]["as_of_date"],
                "total_assets_krw": payload["summary"]["total_assets_krw"],
                "total_cost_krw": payload["summary"]["total_cost_krw"],
                "total_unrealized_pnl_krw": payload["summary"]["total_unrealized_pnl_krw"],
                "total_return_pct": payload["summary"]["total_return_pct"],
                "returns": payload["returns"],
                "mdd": payload["mdd"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
