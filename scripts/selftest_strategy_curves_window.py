"""先.一三五-1ia：策略曲線「建倉日不在價格視窗」時的行為自測（零外部請求、不改本體）。

背景（先.一三五-1hx）：price_history 每檔只留 90 個交易日，`build_strategy_curves.py` 每次從頭重算，
`Px.idx()` 用精確比對找建倉日——建倉日滾出視窗後 `paper_line_from_log()` 回 None，
`paper_lines()` 再把那條線換成「XX 開始」的未起跑佔位。

本自測記錄「現況」，當 1hx 修法的回歸基準：
  ① 建倉日在視窗內 → 曲線從建倉日起算
  ② 建倉日早於視窗第一天 → 1hx 甲（2026-11-04 [預設放行]）起改從視窗內第一個帳本事件重算（原期望回 None）
  ⑤ 1hx 甲 舊點凍結：短視窗重算＋上一版曲線接縫後，要與長視窗一次算完的曲線逐點相同（紙上追蹤／三榜），接縫不跳點；
     接不上時整條沿用上一版、不變回未起跑；上一版起點仍在視窗內就完全用重算；上一版檔讀不出來就不覆蓋
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
    check("② 建倉日早於視窗 → 從視窗內第一個事件重算（1hx 甲）",
          bool(out2) and out2["dates"][0] == days[10] and out2["nav"][0] == 1_050_000.0,
          f"起點 {out2['dates'][0] if out2 else None}")

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

    freeze_tests()

    n_fail = results.count(False)
    print(f"\n合計 {len(results)} 項：PASS {results.count(True)}／FAIL {n_fail}")
    return 1 if n_fail else 0


def _sub(px: B.Px, k: int) -> B.Px:
    """把價格視窗往前推 k 天（丟掉最早 k 個交易日），模擬 90 日滾動。"""
    q = B.Px({"prices": {}})
    q.rows = {c: {d: v for d, v in m.items() if d >= px.cal[k]} for c, m in px.rows.items()}
    q.cal = px.cal[k:]
    return q


def _close(a: list, b: list, tol: float = 2e-3) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def freeze_tests() -> None:
    import json, tempfile
    px, days = make_px(40)
    # 加一檔走勢不同的股票，讓三榜／紙上的日報酬不是單調
    px.rows["2317"] = {d: 100.0 + (7 if i % 3 == 0 else -3) * (i % 5) for i, d in enumerate(days)}

    # ⑤-a 紙上追蹤：長視窗一次算 vs 短視窗＋凍結接縫
    ev = [{"date": days[2], "event": "inception", "values_post": {"2330": 600_000.0, "2317": 400_000.0}},
          {"date": days[15], "event": "rebalance", "values_post": {"2330": 500_000.0, "2317": 560_000.0}},
          {"date": days[28], "event": "rebalance", "values_post": {"2330": 900_000.0, "CASH": 200_000.0}}]
    full_b = B.paper_line_from_log(ev, px)
    full = B._line("paper_7", "G", "paper", "模擬中", full_b["dates"], full_b["nav"], full_b["comp"], px=px)
    prev = json.loads(json.dumps(B._line("paper_7", "G", "paper", "模擬中", *[v[:-3] for v in (full_b["dates"], full_b["nav"], full_b["comp"])], px=px)))
    sp = _sub(px, 8)  # 建倉日 days[2] 滾出；昨天以前的曲線在 prev
    nb = B.paper_line_from_log(ev, sp)
    new = B._line("paper_7", "G", "paper", "模擬中", nb["dates"], nb["nav"], nb["comp"], px=sp)
    m = B.apply_freeze([new], {"lines": [prev]}, sp)[0]
    check("⑤-a 紙上：重算段從視窗內第一個事件起算", new["dates"][0] == days[15], new["dates"][0])
    check("⑤-a 紙上：接縫後日期與長視窗一致", m["dates"] == full["dates"], f"{len(m['dates'])} vs {len(full['dates'])}")
    check("⑤-a 紙上：淨值逐點相同（含接縫）", _close(m["nav"], full["nav"]))
    check("⑤-a 紙上：0050 灰線逐點相同", _close(m["bench"], full["bench"]))
    check("⑤-a 紙上：MDD 與長視窗相同", m["metrics"]["mdd_pct"] == full["metrics"]["mdd_pct"],
          f"{m['metrics']['mdd_pct']} vs {full['metrics']['mdd_pct']}")
    check("⑤-a 紙上：標 frozen_before＝接縫日", m.get("frozen_before") == days[15])

    # ⑤-b 連續滾動多天（每天拿前一班輸出當 prev），最後仍與長視窗相同
    cur = json.loads(json.dumps(B._line("paper_7", "G", "paper", "模擬中", *[v[:-12] for v in (full_b["dates"], full_b["nav"], full_b["comp"])], px=px)))
    for k in range(1, 13):
        q = _sub(px, k)
        q.cal = px.cal[k:len(px.cal) - 12 + k]
        q.rows = {c: {d: v for d, v in mm.items() if d in set(q.cal)} for c, mm in q.rows.items()}
        b = B.paper_line_from_log(ev, q)
        ln = B._line("paper_7", "G", "paper", "模擬中", b["dates"], b["nav"], b["comp"], px=q)
        cur = json.loads(json.dumps(B.apply_freeze([ln], {"lines": [cur]}, q)[0]))
    check("⑤-b 紙上：逐日滾 12 班後仍與長視窗逐點相同", cur["dates"] == full["dates"] and _close(cur["nav"], full["nav"]),
          f"{len(cur['dates'])} 點")

    # ⑤-c 三榜：每天一批
    led = {"snapshots": [{"board": "value", "snapshot_date": d, "taken_at": d,
                          "picks": [{"code": "2330", "entry_date": d, "entry_price": 1}, {"code": "2317", "entry_date": d, "entry_price": 1}]}
                         for d in days[3:]]}
    fr = B.board_line("value", led, px)
    fullb = B._line("board_value", "估值榜", "board", "未回測", fr["dates"], fr["nav"], fr["comp"], px=px)
    pr = B.board_line("value", led, _sub(px, 0))
    pr = {k: v[:-2] if isinstance(v, list) else v for k, v in pr.items()}
    prevb = json.loads(json.dumps(B._line("board_value", "估值榜", "board", "未回測", pr["dates"], pr["nav"], pr["comp"], px=px)))
    sb = _sub(px, 10)
    nr = B.board_line("value", led, sb)
    newb = B._line("board_value", "估值榜", "board", "未回測", nr["dates"], nr["nav"], nr["comp"], px=sb)
    mb = B.apply_freeze([newb], {"lines": [prevb]}, sb)[0]
    check("⑤-c 三榜：接縫日跳過前 HOLD 天暖機", mb.get("frozen_before") == sb.cal[B.HOLD], str(mb.get("frozen_before")))
    check("⑤-c 三榜：淨值逐點與長視窗相同", mb["dates"] == fullb["dates"] and _close(mb["nav"], fullb["nav"]))
    check("⑤-c 三榜：成分最大漲跌幅欄長度對齊", len(mb["comp_max_abs_pct"]) == len(mb["dates"]))

    # ⑤-d 視窗內接不上（重算不出 → 佔位）→ 整條沿用上一版，不變回未起跑
    ph = B._placeholder("paper_7", "G", "paper", "模擬中", "2026-11-02", "11/02 開始")
    k = B.apply_freeze([ph], {"lines": [prev]}, sp)[0]
    check("⑤-d 接不上 → 沿用上一版並標 frozen_note", k.get("started") is True and k["dates"] == prev["dates"] and "frozen_note" in k)

    # ⑤-e 上一版起點仍在視窗內、重算起點變晚（算法更正）→ 完全用重算，不沿用舊點
    late = B._line("paper_7", "G", "paper", "模擬中", full["dates"][5:], full_b["nav"][5:], full_b["comp"][5:], px=px)
    e = B.apply_freeze([late], {"lines": [full]}, px)[0]
    check("⑤-e 上一版起點在視窗內 → 用重算（不殘留舊點）", e["dates"] == late["dates"] and "frozen_before" not in e)

    # ⑤-f 非紙上／三榜的線（真錢佔位）不動
    lv = B._placeholder("live_bb90", "自動投資", "live", "真錢", None, "x")
    check("⑤-f 真錢線不參與凍結", B.apply_freeze([lv], {"lines": [prev | {"id": "live_bb90", "group": "live"}]}, sp)[0] is lv)

    # ⑤-g 上一版檔壞掉 → load_prev 拒絕（main 不覆蓋）；不存在 → None
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "strategy_curves.json"
        bad.write_text("{壞掉", encoding="utf-8")
        try:
            B.load_prev(bad)
            ok = False
        except SystemExit:
            ok = True
        check("⑤-g 上一版壞掉 → SystemExit 不覆蓋", ok and bad.read_text(encoding="utf-8") == "{壞掉")
        check("⑤-g 上一版不存在 → None", B.load_prev(Path(td) / "none.json") is None)
    src = (ROOT / ".github" / "scripts" / "build_strategy_curves.py").read_text(encoding="utf-8")
    check("⑤-h main() 先讀上一版再算", src.index("o = load_prev(OUT)") < src.index("doc = build(o)"))


if __name__ == "__main__":
    raise SystemExit(main())
