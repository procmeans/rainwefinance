#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download A-share valuation and income-statement data.

Outputs:
- stock_list.csv
- valuations/<code>_<name>_valuation.csv
- profits/by_report_date/<YYYYMMDD>_income.csv
- profits/net_profit_all.csv
- errors.csv
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import re
import time
from datetime import date
from pathlib import Path

import akshare as ak
import pandas as pd


def safe_name(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", str(value)).strip("_")


def report_dates(start_year: int, end_year: int) -> list[str]:
    suffixes = ("0331", "0630", "0930", "1231")
    return [f"{year}{suffix}" for year in range(start_year, end_year + 1) for suffix in suffixes]


def write_error(path: Path, scope: str, code: str, name: str, error: Exception) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["scope", "code", "name", "error"])
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "scope": scope,
                "code": code,
                "name": name,
                "error": f"{type(error).__name__}: {error}",
            }
        )


def fetch_stock_list(out_dir: Path) -> pd.DataFrame:
    stock_list = ak.stock_info_a_code_name()
    stock_list["code"] = stock_list["code"].astype(str).str.zfill(6)
    stock_list.drop_duplicates(subset=["code"], inplace=True, ignore_index=True)
    stock_list.to_csv(out_dir / "stock_list.csv", index=False, encoding="utf-8-sig")
    return stock_list


def fetch_one_valuation(row: dict, valuation_dir: Path, errors_path: Path, overwrite: bool) -> str:
    code = str(row["code"]).zfill(6)
    name = str(row["name"])
    output_path = valuation_dir / f"{code}_{safe_name(name)}_valuation.csv"
    if output_path.exists() and not overwrite:
        return f"skip {code} {name}"
    try:
        df = ak.stock_value_em(symbol=code)
        df.insert(0, "股票代码", code)
        df.insert(1, "股票简称", name)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return f"ok {code} {name} rows={len(df)}"
    except Exception as exc:  # noqa: BLE001 - batch jobs should continue.
        write_error(errors_path, "valuation", code, name, exc)
        return f"fail {code} {name}: {type(exc).__name__}"


def fetch_valuations(
    stocks: pd.DataFrame,
    out_dir: Path,
    workers: int,
    sleep_seconds: float,
    overwrite: bool,
) -> None:
    valuation_dir = out_dir / "valuations"
    valuation_dir.mkdir(parents=True, exist_ok=True)
    errors_path = out_dir / "errors.csv"

    rows = stocks[["code", "name"]].to_dict("records")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for row in rows:
            futures.append(
                executor.submit(fetch_one_valuation, row, valuation_dir, errors_path, overwrite)
            )
            if sleep_seconds:
                time.sleep(sleep_seconds)
        for idx, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            print(f"[valuation {idx}/{len(futures)}] {future.result()}", flush=True)


def fetch_profits(out_dir: Path, start_year: int, end_year: int, overwrite: bool) -> None:
    profit_dir = out_dir / "profits" / "by_report_date"
    profit_dir.mkdir(parents=True, exist_ok=True)
    errors_path = out_dir / "errors.csv"
    frames: list[pd.DataFrame] = []

    for report_date in report_dates(start_year, end_year):
        output_path = profit_dir / f"{report_date}_income.csv"
        if output_path.exists() and not overwrite:
            df = pd.read_csv(output_path)
            frames.append(df)
            print(f"[profit] skip {report_date} rows={len(df)}", flush=True)
            continue
        try:
            df = ak.stock_lrb_em(date=report_date)
            df.insert(0, "报告期", report_date)
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            frames.append(df)
            print(f"[profit] ok {report_date} rows={len(df)}", flush=True)
        except Exception as exc:  # noqa: BLE001 - some future periods may be unavailable.
            write_error(errors_path, "profit", report_date, "", exc)
            print(f"[profit] fail {report_date}: {type(exc).__name__}", flush=True)

    if frames:
        profit_all = pd.concat(frames, ignore_index=True)
        net_profit_cols = ["报告期", "股票代码", "股票简称", "净利润", "净利润同比", "公告日期"]
        existing_cols = [col for col in net_profit_cols if col in profit_all.columns]
        profit_all[existing_cols].to_csv(
            out_dir / "profits" / "net_profit_all.csv",
            index=False,
            encoding="utf-8-sig",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/a_share_fundamentals")
    parser.add_argument("--limit", type=int, default=None, help="Limit stock count for testing.")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-valuations", action="store_true")
    parser.add_argument("--skip-profits", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    stocks = fetch_stock_list(out_dir)
    if args.limit:
        stocks = stocks.head(args.limit).copy()
    print(f"stocks={len(stocks)} out={out_dir}", flush=True)

    if not args.skip_valuations:
        fetch_valuations(stocks, out_dir, args.workers, args.sleep, args.overwrite)
    if not args.skip_profits:
        fetch_profits(out_dir, args.start_year, args.end_year, args.overwrite)


if __name__ == "__main__":
    main()
