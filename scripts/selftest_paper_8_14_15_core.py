# -*- coding: utf-8 -*-
"""自測：模擬 N（paper_14）`atr_wilder()`／`grid_params()`、模擬 O（paper_15）`target_weights()`／`score_industries()`、
模擬 H（paper_8）`rebalance_from_ranking()`／`predict_ranking()` 的手算可驗案例（先.一三五-1av-a）。

既有涵蓋：N 的 grid_params 已經被 selftest_paper_13_18 經 process_day() 間接跑過（只驗狀態機，沒有手算數字）；
O 的 target_weights／score_industries、H 的 rebalance_from_ranking／predict_ranking 沒有任何自測直接或經 step() 跑過
（selftest_paper_15 第 5 項 step() 停在 NOT_STARTED、不會走到選股；selftest_paper_8_features 只驗特徵）。
全部合成資料、零網路請求、不讀真實價格；只驗計算規則，**不印任何淨值或報酬**（H 的 inception 案例用合成 100 萬只驗成本解法）。

N1 atr_wilder：TR 固定 2 → 2；最後一根 TR＝42 → (2×19＋42)÷20＝4.0；TR 用前收（跳空列 h＝l＝c 也算進 |h−前收|）；不足 N+1 列 → None。
N2 grid_params：中心＝近 60 個收盤平均、漂移＝|MA60(t)−MA60(t−20)|、`t` 之後的列不進來、還原因子同乘、不足 80 列 → None。
O1 target_weights：取前 1/4 產業（四捨五入、至少 1）、產業內依前一交易日原始收盤×股數、合計 70%；不在 active／當天無價／無股數者排除。
O2／H2 模型雜湊不符 → 拒絕預測（RuntimeError），不載入模型。
H1 rebalance_from_ranking 首次建倉：取前 30 名、等權解出 t＝INITIAL÷30÷(1＋BUY)、成本＝買進額×BUY；空排名 → RuntimeError。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd  # noqa: E402

import paper_forward_common as C  # noqa: E402
import paper_14_grid_range_tracker as N  # noqa: E402
import paper_15_ml_industry_tracker as O  # noqa: E402
import paper_8_ml_tracker as H  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def days(n: int, start: str = "2026-01-05") -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, periods=n)]


def test_atr():
    n = N.N
    check(n == 20 and N.MA_N == 60, f"常數 N＝20、MA_N＝60（實際 {n}／{N.MA_N}）")
    flat = [(101.0, 99.0, 100.0)] * (n + 1)
    check(math.isclose(N.atr_wilder(flat) or 0, 2.0), "TR 固定 2 → ATR 2")
    jump = flat + [(141.0, 99.0, 120.0)]
    check(math.isclose(N.atr_wilder(jump) or 0, 4.0), f"最後 TR＝42 → (2×19＋42)÷20＝4.0（實際 {N.atr_wilder(jump)}）")
    gap = [(101.0, 99.0, 100.0)] * n + [(90.0, 90.0, 90.0)]  # 第 21 列（tr[20]）＝|90−100|＝10
    want = (2.0 * (n - 1) + 10.0) / n
    check(math.isclose(N.atr_wilder(gap) or 0, want), f"跳空列 TR 用前收（{want}）")
    check(N.atr_wilder(flat[:n]) is None, "只有 N 列 → None")


def grid_px(adj_factor: float = 1.0):
    ds = days(N.MA_N + N.N + 5)
    rows = []
    for i, d in enumerate(ds):
        c = 100.0 if i < N.N else 110.0
        if i >= N.MA_N + N.N:
            c = 999.0  # t 之後的列，不得被讀進來
        r = {"date": d, "open": c, "high": c + 1, "low": c - 1, "close": c}
        if adj_factor != 1.0:
            r["adj_close"] = c * adj_factor
        rows.append(r)
    return C.Px({"1234": rows}), ds


def test_grid_params():
    px, ds = grid_px()
    t = ds[N.MA_N + N.N - 1]  # 第 80 列（含）
    gp = N.grid_params(px, "1234", t)
    want_drift = abs(110.0 - (N.N * 100.0 + (N.MA_N - N.N) * 110.0) / N.MA_N)
    check(gp is not None and math.isclose(gp[0], 110.0), f"中心＝近 60 收盤平均 110（實際 {gp and gp[0]}）")
    check(gp is not None and math.isclose(gp[2], want_drift), f"漂移＝|MA60(t)−MA60(t−20)|＝{want_drift:.6f}")
    check(gp is not None and gp[1] > 0 and gp[1] < 3, "ATR 只用到 t 為止（t 之後 999 的列沒進來）")
    check(N.grid_params(px, "1234", ds[N.MA_N + N.N - 2]) is None, "只有 79 列 → None")
    px2, _ = grid_px(0.5)
    gp2 = N.grid_params(px2, "1234", t)
    check(gp2 is not None and math.isclose(gp2[0], 55.0) and math.isclose(gp2[1], gp[1] * 0.5),
          "還原因子 0.5 → 中心與 ATR 同乘 0.5")


def test_target_weights():
    check(O.TOP_FRAC == 0.25 and O.INVEST_FRAC == 0.70, "常數 TOP_FRAC＝0.25、INVEST_FRAC＝0.70")
    d0, d1 = days(2)
    prices = {}
    def put(code, prev_close, today=True):
        prices[code] = [{"date": d0, "close": prev_close}] + ([{"date": d1, "close": prev_close}] if today else [])
    put("a1", 10.0); put("a2", 20.0); put("a3", 30.0); put("a4", 40.0, today=False); put("b1", 50.0)
    px = C.Px(prices)
    ind_of = {"a1": "A", "a2": "A", "a3": "A", "a4": "A", "b1": "B"}
    shares = {"a1": 100, "a2": 150, "a3": 0, "a4": 100, "b1": 100}
    ranked = [{"industry": x, "score": 1.0 - i / 10} for i, x in enumerate(["A", "B", "C", "D", "E"])]  # 5 個 → k＝int(1.75)＝1
    out = O.target_weights(ranked, px, d1, ind_of, shares, active={"a1", "a2", "a3", "a4", "b1"})
    w = {r["code"]: r["weight"] for r in out}
    check(set(w) == {"a1", "a2"}, f"5 個產業只取第 1 個；a3 無股數、a4 當天無價排除（實際 {sorted(w)}）")
    check(math.isclose(w.get("a1", 0), 0.70 * 1000 / 4000) and math.isclose(w.get("a2", 0), 0.70 * 3000 / 4000),
          "產業內依前一日原始收盤×股數（1000：3000）")
    out2 = O.target_weights(ranked, px, d1, ind_of, shares, active={"a2", "b1"})
    check({r["code"] for r in out2} == {"a2"} and math.isclose(out2[0]["weight"], 0.70), "不在 active 的排除、合計 70%")
    ranked8 = [{"industry": x, "score": 1.0 - i / 10} for i, x in enumerate("ABCDEFGH")]  # 8 個 → k＝int(2.5)＝2
    out3 = O.target_weights(ranked8, px, d1, ind_of, shares, active={"a1", "a2", "b1"})
    tot = sum(r["weight"] for r in out3)
    check(math.isclose(tot, 0.70) and {r["industry"] for r in out3} == {"A", "B"}, "8 個產業取前 2、兩產業各 35%、合計 70%")


def test_model_hash_refusal():
    for name, mod, call in (("模擬 O score_industries", O, lambda: O.score_industries({}, {}, "2027-01-04", {"model_sha256": "0" * 64})),
                            ("模擬 H predict_ranking", H, lambda: H.predict_ranking([], {"model_sha256": "0" * 64}))):
        if not mod.MODEL_PATH.exists():
            print(f"SKIP {name}：本機沒有模型檔 {mod.MODEL_PATH.name}（雜湊檢查需要檔案存在）")
            continue
        try:
            call()
            check(False, f"{name}：雜湊不符應拒絕")
        except RuntimeError as e:
            check("雜湊" in str(e), f"{name}：雜湊不符 → RuntimeError 拒絕預測")


def test_rebalance_inception():
    import paper_7_revsurprise_tracker as G
    check(H.TOP_N == 30 and H.EXIT_RANK == 90, "常數 TOP_N＝30、EXIT_RANK＝90")
    rk = [{"code": f"{1000 + i}", "score": 1.0 - i / 100, "rank": i + 1, "turnover_20d": 1e8} for i in range(40)]
    r = H.rebalance_from_ranking(rk, None, "2026-12-01", None)
    t = H.INITIAL / H.TOP_N / (1 + G.BUY)
    check(r["event"] == "inception" and r["entered"] == [x["code"] for x in rk[:30]] and r["exited"] == [],
          "首次建倉取前 30 名、無出場")
    check(all(abs(v - t) <= 0.01 for v in r["values_post"].values()), "等權每檔＝INITIAL÷30÷(1＋BUY)")
    check(abs(r["rebalance_cost"] - 30 * t * G.BUY) <= 0.05 and abs(r["nav"] + r["rebalance_cost"] - H.INITIAL) <= 0.5,
          "成本＝買進額×BUY、建倉後淨值＋成本＝初始資金")
    try:
        H.rebalance_from_ranking([], None, "2026-12-01", None)
        check(False, "空排名應拒絕建倉")
    except RuntimeError:
        check(True, "空排名 → RuntimeError（不建倉）")


def main() -> int:
    test_atr()
    test_grid_params()
    test_target_weights()
    test_model_hash_refusal()
    test_rebalance_inception()
    print(f"\n結果：{'全部通過' if not FAILS else f'{len(FAILS)} 項 FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
