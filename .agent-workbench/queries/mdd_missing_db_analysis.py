#!/usr/bin/env python3
"""Analyze known MDD missing/partial snapshot dates from the read-only DB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / ".agent-workbench" / "config.json"
DEFAULT_DATES = ("2026-03-26", "2026-04-05", "2026-05-05")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--target", default="prod_readonly")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def make_engine(config_path: Path, target: str):
    with config_path.open(encoding="utf-8") as file:
        config = json.load(file)["db_targets"][target]

    url = (
        f"{config['driver']}://{config['user']}:{quote_plus(config['password'])}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )
    return create_engine(url, connect_args={"connect_timeout": 5})


def mdd(series: list[dict]) -> dict:
    peak_date = None
    peak_value = None
    worst_pct = 0.0
    worst = None

    for point in series:
        value = float(point["total"])
        if peak_value is None or value > peak_value:
            peak_date = point["day"]
            peak_value = value

        drawdown_pct = (value / peak_value - 1.0) * 100.0 if peak_value else 0.0
        if drawdown_pct < worst_pct:
            worst_pct = drawdown_pct
            worst = {
                "peak_date": peak_date,
                "trough_date": point["day"],
                "peak_value": peak_value,
                "trough_value": value,
                "maximum_drawdown_pct": worst_pct,
            }

    return worst or {
        "peak_date": peak_date,
        "trough_date": peak_date,
        "peak_value": peak_value,
        "trough_value": peak_value,
        "maximum_drawdown_pct": 0.0,
    }


def analyze(engine) -> dict:
    target_dates = list(DEFAULT_DATES)
    neighbor_dates = [
        "2026-03-25",
        "2026-03-26",
        "2026-03-27",
        "2026-04-04",
        "2026-04-05",
        "2026-04-06",
        "2026-05-04",
        "2026-05-05",
        "2026-05-06",
    ]

    with engine.connect() as conn:
        connection = conn.execute(
            text("select current_database() as database, current_user as user")
        ).mappings().one()

        privileges = {
            "select_daily_asset_metrics": conn.execute(
                text(
                    "select has_table_privilege(:u, :t, :p)"
                ),
                {
                    "u": "ams_readonly",
                    "t": "public.daily_asset_metrics",
                    "p": "SELECT",
                },
            ).scalar(),
            "delete_daily_asset_metrics": conn.execute(
                text(
                    "select has_table_privilege(:u, :t, :p)"
                ),
                {
                    "u": "ams_readonly",
                    "t": "public.daily_asset_metrics",
                    "p": "DELETE",
                },
            ).scalar(),
        }

        platform_summary = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    with latest as (
                      select
                        p.name as platform,
                        date(d.created_at) as day,
                        max(d.revision) as revision
                      from daily_asset_metrics d
                      join platforms p on p.id = d.platform_id
                      where date(d.created_at)::text = any(:days)
                      group by p.name, date(d.created_at)
                    )
                    select
                      l.day::text,
                      l.platform,
                      l.revision,
                      count(*) as rows,
                      round(sum(d.after_value_krw)::numeric, 2)::text as total_krw
                    from latest l
                    join platforms p on p.name = l.platform
                    join daily_asset_metrics d
                      on d.platform_id = p.id
                     and date(d.created_at) = l.day
                     and d.revision = l.revision
                    group by l.day, l.platform, l.revision
                    order by l.day, l.platform
                    """
                ),
                {"days": neighbor_dates},
            ).mappings()
        ]

        kis_rows = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    with latest as (
                      select
                        p.id as platform_id,
                        date(d.created_at) as day,
                        max(d.revision) as revision
                      from daily_asset_metrics d
                      join platforms p on p.id = d.platform_id
                      where p.name = '한국투자증권'
                        and date(d.created_at)::text = any(:days)
                      group by p.id, date(d.created_at)
                    )
                    select
                      l.day::text,
                      l.revision,
                      d.exchange,
                      d.symbol,
                      round(d.after_value_krw::numeric, 2)::text as total_krw
                    from latest l
                    join daily_asset_metrics d
                      on d.platform_id = l.platform_id
                     and date(d.created_at) = l.day
                     and d.revision = l.revision
                    order by l.day, d.exchange nulls last, d.symbol
                    """
                ),
                {"days": neighbor_dates},
            ).mappings()
        ]

        portfolio_series = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    with latest as (
                      select
                        platform_id,
                        date(created_at) as day,
                        max(revision) as revision
                      from daily_asset_metrics
                      where date(created_at) >= current_date - interval '180 days'
                      group by platform_id, date(created_at)
                    )
                    select
                      l.day::text,
                      sum(d.after_value_krw)::float as total
                    from latest l
                    join daily_asset_metrics d
                      on d.platform_id = l.platform_id
                     and date(d.created_at) = l.day
                     and d.revision = l.revision
                    where d.after_value_krw is not null
                    group by l.day
                    order by l.day
                    """
                )
            ).mappings()
        ]

    by_day = {}
    for row in kis_rows:
        by_day.setdefault(row["day"], {})[(row["exchange"], row["symbol"])] = float(
            row["total_krw"]
        )

    neighbor_pairs = {
        "2026-03-26": ("2026-03-25", "2026-03-27"),
        "2026-04-05": ("2026-04-04", "2026-04-06"),
        "2026-05-05": ("2026-05-04", "2026-05-06"),
    }
    missing_by_day = {}
    for day, (previous_day, next_day) in neighbor_pairs.items():
        expected = set(by_day.get(previous_day, {})) | set(by_day.get(next_day, {}))
        actual = set(by_day.get(day, {}))
        missing_by_day[day] = {
            "missing_symbols": sorted(
                [
                    {"exchange": exchange, "symbol": symbol}
                    for exchange, symbol in expected - actual
                ],
                key=lambda item: (str(item["exchange"]), item["symbol"]),
            ),
            "extra_symbols": sorted(
                [
                    {"exchange": exchange, "symbol": symbol}
                    for exchange, symbol in actual - expected
                ],
                key=lambda item: (str(item["exchange"]), item["symbol"]),
            ),
        }

    bad_dates = set(target_dates)
    skip_series = [point for point in portfolio_series if point["day"] not in bad_dates]

    forward_fill_series = []
    last_good = None
    for point in portfolio_series:
        repaired = dict(point)
        if point["day"] in bad_dates and last_good is not None:
            repaired["total"] = last_good
        else:
            last_good = point["total"]
        forward_fill_series.append(repaired)

    linear_series = []
    for index, point in enumerate(portfolio_series):
        repaired = dict(point)
        if point["day"] in bad_dates:
            previous_value = next(
                portfolio_series[i]["total"]
                for i in range(index - 1, -1, -1)
                if portfolio_series[i]["day"] not in bad_dates
            )
            next_value = next(
                portfolio_series[i]["total"]
                for i in range(index + 1, len(portfolio_series))
                if portfolio_series[i]["day"] not in bad_dates
            )
            repaired["total"] = (previous_value + next_value) / 2.0
        linear_series.append(repaired)

    return {
        "connection": dict(connection),
        "privileges": privileges,
        "platform_summary": platform_summary,
        "kis_rows": kis_rows,
        "missing_by_day": missing_by_day,
        "mdd": {
            "raw": mdd(portfolio_series),
            "skip": mdd(skip_series),
            "forward_fill": mdd(forward_fill_series),
            "linear": mdd(linear_series),
        },
    }


def print_text(report: dict) -> None:
    print(f"connection={report['connection']}")
    print(f"privileges={report['privileges']}")
    print("platform_summary")
    for row in report["platform_summary"]:
        print(row)
    print("kis_day_summary")
    for day in sorted({row["day"] for row in report["kis_rows"]}):
        rows = [row for row in report["kis_rows"] if row["day"] == day]
        total = sum(float(row["total_krw"]) for row in rows)
        revisions = sorted({row["revision"] for row in rows})
        symbols = [
            f"{row['exchange'] or 'KR'}:{row['symbol']}={row['total_krw']}"
            for row in rows
        ]
        print(f"{day} count={len(rows)} total={total:.2f} revisions={revisions}")
        print("  " + ", ".join(symbols))
    print("missing_by_day")
    for day, detail in report["missing_by_day"].items():
        print(day, detail)
    print("mdd")
    for name, detail in report["mdd"].items():
        print(name, detail)


def main() -> int:
    args = parse_args()
    report = analyze(make_engine(args.config, args.target))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
