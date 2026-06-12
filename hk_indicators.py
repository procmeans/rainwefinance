#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取全部港股的 PE / 净利润 / 营业收入 / 总市值,合并成一张表。

数据来源(akshare):
  - 代码列表:        stock_hk_spot_em
  - 营收/净利润:     stock_financial_hk_analysis_indicator_em  (最新一期年报)
  - 总市值 / PE(TTM):stock_hk_valuation_baidu                  (取时间序列最后一个值)

特点:
  - 逐只抓取,带重试 + 限速,避免被封;
  - 断点续抓:已抓过的代码会跳过(读已有 CSV);
  - 每抓 N 只落一次盘,中途断了不丢数据。

用法:
  python3 hk_indicators.py              # 抓全部港股
  python3 hk_indicators.py --limit 30   # 只抓前 30 只(先试跑)
  python3 hk_indicators.py --workers 1  # 串行(最稳,默认)
"""

import argparse
import os
import time

import pandas as pd
import akshare as ak

OUT_CSV = "hk_indicators.csv"


def with_retry(func, *args, retries=3, pause=1.0, **kwargs):
    """带重试地调用一个 akshare 接口;全部失败返回 None。"""
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 网络/解析异常都重试
            if i == retries - 1:
                return None
            time.sleep(pause * (i + 1))
    return None


def get_hk_code_list(limit=None):
    """全部港股代码 + 名称(新浪源;东财 push2 域名经常连不上,故用新浪)。"""
    df = with_retry(ak.stock_hk_spot, retries=5, pause=2.0)
    if df is None or df.empty:
        raise RuntimeError("stock_hk_spot 拉取失败,请检查网络后重试")
    df = df.rename(columns={"中文名称": "名称"})[["代码", "名称"]]
    df = df.drop_duplicates("代码").reset_index(drop=True)
    if limit:
        df = df.head(limit)
    return df


def get_revenue_profit(symbol):
    """最新一期年报的营业收入 / 归母净利润 / 报告期 / 币种。"""
    df = with_retry(
        ak.stock_financial_hk_analysis_indicator_em, symbol=symbol, indicator="年度"
    )
    if df is None or df.empty:
        return {}
    row = df.iloc[0]  # 接口已按报告期降序,首行即最新
    return {
        "报告期": str(row.get("REPORT_DATE", ""))[:10],
        "营业收入": pd.to_numeric(row.get("OPERATE_INCOME"), errors="coerce"),
        "净利润": pd.to_numeric(row.get("HOLDER_PROFIT"), errors="coerce"),
        "营收同比%": pd.to_numeric(row.get("OPERATE_INCOME_YOY"), errors="coerce"),
        "净利润同比%": pd.to_numeric(row.get("HOLDER_PROFIT_YOY"), errors="coerce"),
        "ROE%": pd.to_numeric(row.get("ROE_AVG"), errors="coerce"),
        "币种": row.get("CURRENCY", ""),
    }


def _last_value(symbol, indicator):
    df = with_retry(
        ak.stock_hk_valuation_baidu, symbol=symbol, indicator=indicator, period="近一年"
    )
    if df is None or df.empty:
        return None
    return float(df["value"].iloc[-1])


def get_marketcap_pe(symbol):
    """最新总市值(亿,原币)与市盈率(TTM)。"""
    return {
        "总市值_亿": _last_value(symbol, "总市值"),
        "PE_TTM": _last_value(symbol, "市盈率(TTM)"),
    }


def fetch_one(code, name):
    rec = {"代码": code, "名称": name}
    rec.update(get_revenue_profit(code))
    rec.update(get_marketcap_pe(code))
    return rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="只抓前 N 只(试跑用)")
    parser.add_argument("--sleep", type=float, default=0.4, help="每只之间的间隔秒数")
    parser.add_argument("--save-every", type=int, default=20, help="每抓多少只落一次盘")
    args = parser.parse_args()

    codes = get_hk_code_list(limit=args.limit)
    print(f"待抓取港股数量:{len(codes)}")

    # 断点续抓:已存在的结果跳过
    done = set()
    results = []
    if os.path.exists(OUT_CSV):
        old = pd.read_csv(OUT_CSV, dtype={"代码": str})
        results = old.to_dict("records")
        done = set(old["代码"].astype(str))
        print(f"已发现历史结果 {len(done)} 条,将跳过这些代码")

    todo = codes[~codes["代码"].astype(str).isin(done)]
    for i, (_, r) in enumerate(todo.iterrows(), 1):
        code, name = str(r["代码"]), r["名称"]
        rec = fetch_one(code, name)
        results.append(rec)
        mc = rec.get("总市值_亿")
        pe = rec.get("PE_TTM")
        print(f"[{i}/{len(todo)}] {code} {name}  市值={mc}  PE={pe}")

        if i % args.save_every == 0:
            pd.DataFrame(results).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
        time.sleep(args.sleep)

    out = pd.DataFrame(results)
    cols = [
        "代码", "名称", "PE_TTM", "总市值_亿",
        "营业收入", "净利润", "营收同比%", "净利润同比%", "ROE%",
        "报告期", "币种",
    ]
    out = out[[c for c in cols if c in out.columns]]
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n完成,共 {len(out)} 条,已写入 {OUT_CSV}")
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
