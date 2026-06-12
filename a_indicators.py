#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取全部 A 股的 PE(TTM) / 总市值 / 营业收入 / 净利润,合并成一张表。

数据来源(东财数据中心 datacenter-web.eastmoney.com,该域名可直连):
  - 估值(PE_TTM / 总市值): RPT_VALUEANALYSIS_DET 按交易日过滤,翻页拉全市场
  - 营收 / 净利润:          stock_yjbb_em(业绩报表,最新一期年报)

与港股逐只抓不同,A 股两个接口都是全市场批量返回,几十秒即可抓完。

用法:
  python3 a_indicators.py
"""
import datetime
import time

import pandas as pd
import requests
import akshare as ak

OUT_CSV = "a_indicators.csv"
URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
ANNUAL_REPORT_DATE = "20251231"  # 最新一期年报


def dc_get(params, retries=4, pause=1.0):
    for i in range(retries):
        try:
            r = requests.get(URL, params=params, timeout=20)
            j = r.json()
            if j.get("result"):
                return j["result"]
        except Exception:
            pass
        time.sleep(pause * (i + 1))
    return None


def latest_trade_date():
    """估值报表里最新的交易日。"""
    res = dc_get({
        "sortColumns": "TRADE_DATE", "sortTypes": "-1",
        "pageSize": "1", "pageNumber": "1",
        "reportName": "RPT_VALUEANALYSIS_DET", "columns": "TRADE_DATE",
        "source": "WEB", "client": "WEB",
        "filter": '(SECURITY_CODE="000001")',
    })
    if not res:
        raise RuntimeError("拉取最新交易日失败")
    return res["data"][0]["TRADE_DATE"][:10]


def fetch_valuation(trade_date):
    """全市场 PE_TTM / 总市值。"""
    rows, page = [], 1
    while True:
        res = dc_get({
            "sortColumns": "TOTAL_MARKET_CAP", "sortTypes": "-1",
            "pageSize": "500", "pageNumber": str(page),
            "reportName": "RPT_VALUEANALYSIS_DET", "columns": "ALL",
            "source": "WEB", "client": "WEB",
            "filter": f"(TRADE_DATE='{trade_date}')",
        })
        if not res or not res.get("data"):
            break
        rows.extend(res["data"])
        print(f"  估值第 {page}/{res.get('pages')} 页,累计 {len(rows)} 条")
        if page >= int(res.get("pages") or 1):
            break
        page += 1
        time.sleep(0.3)
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "SECURITY_CODE": "代码", "SECURITY_NAME_ABBR": "名称",
        "PE_TTM": "PE_TTM", "TOTAL_MARKET_CAP": "总市值",
    })[["代码", "名称", "PE_TTM", "总市值"]]
    df["代码"] = df["代码"].astype(str)
    df["总市值_亿"] = pd.to_numeric(df["总市值"], errors="coerce") / 1e8
    df["PE_TTM"] = pd.to_numeric(df["PE_TTM"], errors="coerce")
    return df.drop(columns=["总市值"]).drop_duplicates("代码")


def fetch_earnings(report_date):
    """最新年报的营收 / 净利润(东财业绩报表,全市场一次返回)。"""
    df = None
    for i in range(3):
        try:
            df = ak.stock_yjbb_em(date=report_date)
            break
        except Exception:
            time.sleep(2 * (i + 1))
    if df is None or df.empty:
        print("  业绩报表拉取失败,营收/净利润将留空")
        return pd.DataFrame(columns=["代码", "营业收入", "净利润"])
    df = df.rename(columns={
        "股票代码": "代码",
        "营业总收入-营业总收入": "营业收入",
        "净利润-净利润": "净利润",
    })[["代码", "营业收入", "净利润"]]
    df["代码"] = df["代码"].astype(str)
    return df.drop_duplicates("代码")


def main():
    td = latest_trade_date()
    print(f"最新交易日:{td}")
    val = fetch_valuation(td)
    print(f"估值数据 {len(val)} 只")
    earn = fetch_earnings(ANNUAL_REPORT_DATE)
    print(f"业绩数据 {len(earn)} 只(报告期 {ANNUAL_REPORT_DATE})")

    out = val.merge(earn, on="代码", how="left")
    out["报告期"] = f"{ANNUAL_REPORT_DATE[:4]}-{ANNUAL_REPORT_DATE[4:6]}-{ANNUAL_REPORT_DATE[6:]}"
    out["币种"] = "CNY"
    out = out[["代码", "名称", "PE_TTM", "总市值_亿", "营业收入", "净利润", "报告期", "币种"]]
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n完成,共 {len(out)} 条,已写入 {OUT_CSV}")
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
