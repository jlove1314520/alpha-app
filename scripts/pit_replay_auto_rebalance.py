"""先.二十九-二：PIT 快照回放流程檢查表（2026-05～09 五個月底）。
只檢查流程能否在「當時可得資料」下走通：資料可得、目標權重、下單產生、硬限制閘門。
不計算、不輸出任何淨值或報酬。"""
import json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
import auto_rebalance_bb90 as A

MONTH_ENDS = ["2026-05-29", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30"]
OUT = Path(__file__).resolve().parent.parent / "research" / "PIT_REPLAY_AUTO_REBALANCE.md"


def asof_close(rows, d):
    ok = [r for r in rows if r.get("date") and r["date"] <= d and r.get("close")]
    return (float(ok[-1]["close"]), ok[-1]["date"]) if ok else None


def finmind_rows(code):
    import requests
    r = requests.get("https://api.finmindtrade.com/api/v4/data", timeout=30,
                     params={"dataset": "TaiwanStockPrice", "data_id": code,
                             "start_date": "2026-05-01", "end_date": "2026-09-30"}).json()
    return [{"date": x["date"], "close": x["close"]} for x in r.get("data", [])]


def main():
    px = {c: list(rows) for c, rows in ((A._read_json(A.PRICE_HISTORY) or {}).get("prices") or {}).items()}
    used_fm = []
    for c in A.WHITELIST:
        have = {r["date"] for r in px.get(c, [])}
        try:
            extra = [r for r in finmind_rows(c) if r["date"] not in have]
        except Exception as e:
            print(f"[warn] FinMind 補資料失敗 {c}：{e}")
            extra = []
        if extra:
            used_fm.append(c)
        px[c] = sorted(px.get(c, []) + extra, key=lambda r: r["date"])
    cfg = {"per_order_cap_twd": 1_500_000, "max_price_dev_pct": 1.0, "max_data_age_days": 4}
    lines = ["# 先.二十九-二 PIT 快照回放流程檢查表（Bb-90 自動再平衡）", "",
             "只檢查流程；不含任何淨值、報酬或績效數字。假設每次用 100 萬新資金、零既有持股，僅用於走通流程。", "",
             "| 月底 | 三檔資料可得(≤該日) | 資料新鮮度≤4日 | 無未來資料 | 目標權重加總=100% | 產生下單 | 硬限制閘門全過 | 結論 |",
             "|---|---|---|---|---|---|---|---|"]
    allpass = True
    for me in MONTH_ENDS:
        d = date.fromisoformat(me)
        prev = {c: asof_close(px.get(c, []), me) for c in A.WHITELIST}
        avail = all(prev.values())
        fresh = avail and all((d - date.fromisoformat(v[1])).days <= 4 for v in prev.values())
        nofuture = avail and all(v[1] <= me for v in prev.values())
        wsum = abs(sum(A.WEIGHTS.values()) - 1.0) < 1e-9
        orders, gate_ok = [], False
        if avail:
            orders = A.plan_orders({c: prev[c][0] for c in A.WEIGHTS}, {}, 1_000_000, odd_ok=True,
                                   dev_pct=cfg["max_price_dev_pct"] / 2)
            ctx = {"cfg": cfg, "prev_close": prev, "today": d, "stopped": False, "reconciled": True}
            gate_ok = bool(orders) and all(not A.gate_order(o, ctx) for o in orders)
        res = [avail, fresh, nofuture, wsum, bool(orders), gate_ok]
        p = all(res)
        allpass &= p
        f = lambda b: "PASS" if b else "FAIL"
        lines.append(f"| {me} | {f(avail)} | {f(fresh)} | {f(nofuture)} | {f(wsum)} | {f(bool(orders))} | {f(gate_ok)} | {f(p)} |")
    lines += ["", f"整體：{'PASS' if allpass else 'FAIL'}", "",
              f"限制：資料來源為 data/price_history.json（僅約 90 列滾動窗，00646／00697B 在 2025-01 至 2026-05 之間有缺口）加 FinMind TaiwanStockPrice 補缺（補資料標的：{used_fm or '無'}）；as-of 收盤；未回放券商對帳與實際成交（無歷史券商狀態可回放）。"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
