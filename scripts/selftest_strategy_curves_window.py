"""先.一三五-1ia：策略曲線「建倉日不在價格視窗」時的行為自測（零外部請求、不改本體）。

背景（先.一三五-1hx）：price_history 每檔只留 90 個交易日，`build_strategy_curves.py` 每次從頭重算，
`Px.idx()` 用精確比對找建倉日——建倉日滾出視窗後 `paper_line_from_log()` 回 None，
`paper_lines()` 再把那條線換成「XX 開始」的未起跑佔位。

本自測記錄「現況」，當 1hx 修法的回歸基準：
  ① 建倉日在視窗內 → 曲線從建倉日起算
  ② 建倉日早於視窗第一天 → 現況回 None（1hx 修法上線後要改成曲線仍完整，屆時改這一項的期望值）
  ③ 建倉日是休市日（不在 0050 日曆）→ 現況回 None
  ④ 帳本事件缺 values_post 也缺 nav → 本函式回一條淨值全 0 的線（不拋例外）；原本 paper_lines() 接著呼叫的 _line()
     歸一化除以 0、且不在 try 裡，整份 strategy_curves.json 這班不寫——1ia 已修成只讓那一條改顯示未起跑（十二節）
用合成資料，不讀 data/、不連網。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import build_strategy_curves as B  # noqa: E402

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"：{detail}" if detail else ""))


def make_px(n_days: int = 30, start: date = date(2027, 1, 4)) -> tuple[B.Px, list]:
    days, d = [], start
    while len(days) < n_days:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    prices = {
        B.BENCH: [{"date": x, "close": 100.0 + i, "adj_close": 100.0 + i} for i, x in enumerate(days)],
        "2330": [{"date": x, "close": 500.0 + 2 * i, "adj_close": 500.0 + 2 * i} for i, x in enumerate(days)],
    }
    return B.Px({"prices": prices}), days


def main() -> int:
    px, days = make_px()

    # ① 建倉日在視窗內
    ev = [{"date": days[5], "event": "inception", "values_post": {"2330": 1_000_000.0}, "rebalance_cost": 1.0}]
    out = B.paper_line_from_log(ev, px)
    check("① 建倉日在視窗內 → 曲線從建倉日起算",
          bool(out) and out["dates"][0] == days[5] and len(out["dates"]) == len(days) - 5,
          f"起點 {out['dates'][0] if out else None}、{len(out['dates']) if out else 0} 點")

    # ② 建倉日早於視窗第一天（模擬滾出 90 日視窗）
    ev2 = [{"date": "2026-11-02", "event": "inception", "values_post": {"2330": 1_000_000.0}, "rebalance_cost": 1.0},
           {"date": days[10], "event": "rebalance", "values_post": {"2330": 1_050_000.0}}]
    out2 = B.paper_line_from_log(ev2, px)
    check("② 建倉日早於視窗 → 現況回 None（整條消失；1hx 修法後改期望）", out2 is None, f"回傳 {type(out2).__name__}")

    # ③ 建倉日是週六（不在 0050 日曆）
    sat = next(x for x in (date.fromisoformat(days[0]) + timedelta(days=k) for k in range(10)) if x.weekday() == 5).isoformat()
    ev3 = [{"date": sat, "event": "inception", "values_post": {"2330": 1_000_000.0}, "rebalance_cost": 1.0}]
    out3 = B.paper_line_from_log(ev3, px)
    check("③ 建倉日是休市日 → 現況回 None", out3 is None, f"{sat} 回傳 {type(out3).__name__}")

    # ④ 事件缺 values_post 也缺 nav
    ev4 = [{"date": days[2], "event": "inception"}]
    out4 = B.paper_line_from_log(ev4, px)
    check("④ 壞事件 → 本函式回淨值全 0 的線（現況）", bool(out4) and set(out4["nav"]) == {0}, f"前 3 點 {out4['nav'][:3] if out4 else None}")
    try:
        B._line("x", "x", "paper", "模擬中", out4["dates"], out4["nav"], out4["comp"], px=px)
        raised = None
    except Exception as e:  # noqa: BLE001
        raised = type(e).__name__
    check("④-b 這條線直接進 _line() 會除以 0（所以 paper_lines() 要先擋）", raised == "ZeroDivisionError", f"拋 {raised}")

    # ④-c paper_lines() 整體：一條壞帳本只讓那條變佔位，其他線照常
    import tempfile, json
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.jsonl"
        good = Path(td) / "good.jsonl"
        bad.write_text(json.dumps(ev4[0]) + "\n", encoding="utf-8")
        good.write_text(json.dumps(ev[0]) + "\n", encoding="utf-8")
        orig = B.RDATA
        B.RDATA = Path(td)
        specs_src = (ROOT / ".github" / "scripts" / "build_strategy_curves.py").read_text(encoding="utf-8")
        try:
            # 把 paper_7 指到壞帳本、paper_1b 指到好帳本，其餘不存在（_jsonl 讀不到回空）
            real_jsonl = B._jsonl
            B._jsonl = lambda p: real_jsonl(bad if "paper_7_log" in str(p) else good if "paper_1b_log" in str(p) else Path(td) / "none.jsonl")
            try:
                lines = B.paper_lines(px)
                err = None
            except Exception as e:  # noqa: BLE001
                lines, err = [], f"{type(e).__name__}: {e}"
        finally:
            B._jsonl = real_jsonl
            B.RDATA = orig
    by = {l["id"]: l for l in lines}
    check("④-c paper_lines() 不因一條壞帳本整批失敗", err is None, err or f"{len(lines)} 條")
    check("④-d 壞帳本那條（paper_7）改顯示未起跑", by.get("paper_7", {}).get("started") is False)
    check("④-e 好帳本那條（paper_1b）照常有曲線", by.get("paper_1b", {}).get("started") is True)
    check("④-f 修法註記存在", "先.一三五-1ia" in specs_src)

    n_fail = results.count(False)
    print(f"\n合計 {len(results)} 項：PASS {results.count(True)}／FAIL {n_fail}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
