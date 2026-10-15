"""先.一〇三-1（2026-10-15）：data/market_tw.json 三大法人全市場合計重產＋合理性驗證。

舊版 T86 用 selectType=ALL（含權證），自營商權證避險部位把全市場合計撐到失真
（10/15 自營商 −434 萬張）。fetch_market_tw.py 已改 ALLBUT0999、外資含外資自營商；
這支把 institutional_history 現有日期（最多 10 天）用新口徑重抓一次並覆寫，
再用 TWSE FMTQIK（當月每日全市場成交股數）驗證：每一天外資／投信／自營商／合計的
絕對值都必須小於當日全市場成交量，任何一天不過就不寫檔、exit 1。

請求：T86 每個日期 1 次（twse_t86，間隔 ≥3 秒）＋ FMTQIK 每個月份 1 次（twse_rwd），
共用 data/rate_limit_state.json 節流，402/403/428/429 封鎖 2 小時不重試。
用法：python scripts/fix_institutional_allbut0999.py [--dry-run]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import fetch_market_tw as M  # noqa: E402

FMTQIK_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
KEYS = ("foreign_net_lots", "trust_net_lots", "dealer_net_lots", "total_net_lots")


def market_volume_lots(yyyymm: str) -> dict[str, float]:
    """回傳 {YYYYMMDD: 當日全市場成交張數}（FMTQIK 成交股數 ÷ 1000）。"""
    M._rate_limit_wait_or_raise("twse_rwd")
    r = requests.get(FMTQIK_URL, params={"date": yyyymm + "01", "response": "json"},
                     headers={"User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)"}, timeout=20)
    if r.status_code in (402, 403, 428, 429):
        M._rate_limit_record_block("twse_rwd", r.status_code, r.text[:200])
        raise RuntimeError(f"FMTQIK HTTP {r.status_code}")
    r.raise_for_status()
    body = r.json()
    fields = body.get("fields") or []
    i_d, i_v = fields.index("日期"), fields.index("成交股數")
    out = {}
    for row in body.get("data") or []:
        y, m, d = row[i_d].strip().split("/")
        out[f"{int(y) + 1911}{int(m):02d}{int(d):02d}"] = float(row[i_v].replace(",", "")) / 1000
    return out


def main() -> int:
    dry = "--dry-run" in sys.argv
    path = ROOT / "data" / "market_tw.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hist = data.get("institutional_history") or []
    dates = [h["date"] for h in hist]
    print(f"重產 {len(dates)} 天：{dates}")
    vols: dict[str, float] = {}
    for ym in sorted({d[:6] for d in dates}):
        vols.update(market_volume_lots(ym))
    new_hist, ok = [], True
    for h in hist:
        _, inst = M.fetch_institutional_aggregate(h["date"])
        if inst is None:
            print(f"  {h['date']} T86 無資料，保留舊值並標 scope=舊口徑")
            new_hist.append({**h, "scope": "舊口徑（含權證），重抓無資料"})
            continue
        vol = vols.get(h["date"])
        bad = [k for k in KEYS if vol is None or abs(inst[k]) >= vol]
        ok &= not bad
        print(f"  {h['date']} 外資 {h['foreign_net_lots']:>12,.0f}→{inst['foreign_net_lots']:>12,.0f}"
              f"  投信 {h['trust_net_lots']:>10,.0f}→{inst['trust_net_lots']:>10,.0f}"
              f"  自營 {h['dealer_net_lots']:>12,.0f}→{inst['dealer_net_lots']:>12,.0f}"
              f"  合計 {h['total_net_lots']:>12,.0f}→{inst['total_net_lots']:>12,.0f}"
              f"  成交量 {vol or 0:>12,.0f}  {'PASS' if not bad else 'FAIL ' + ','.join(bad)}")
        if vol:
            inst["market_volume_lots"] = round(vol, 1)
        new_hist.append(inst)
    if not ok:
        print("合理性驗證失敗：有欄位絕對值 ≥ 當日全市場成交量，不寫檔")
        return 1
    if dry:
        print("--dry-run：驗證通過，不寫檔")
        return 0
    data["institutional_history"] = new_hist
    last = new_hist[-1] if new_hist else None
    if last and data.get("institutional", {}).get("date") == last["date"]:
        data["institutional"] = last
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫回 {path.relative_to(ROOT)}（institutional_history {len(new_hist)} 天）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
