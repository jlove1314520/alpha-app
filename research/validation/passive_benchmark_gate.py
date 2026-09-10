"""Gate 8：被動基準強制對照組（`PENDING_QUEUE.md` 深讀二.2，取代六關第2關）。

**這個檔案解決什麼問題**：`research/passive_benchmark_tw_v1.py`（深讀二.1）已經算出
「固定小倉位持有0050、真實權重漂移＋照實收成本再平衡」在 w=0.08~0.30 這 12 個風險
水準下，TRAIN／VAL 兩期各自的報酬／MDD／Sortino——但那份結果只是一個 JSON 檔，沒有
任何候選評估流程真的在讀它。`MARATHON_PROTOCOL.md` 第 321~326 行原本白紙黑字寫著
「深讀二.1／二.2完成前這關無法真正生效」。這支模組就是讓它「真正生效」的那段程式碼：
接下來任何候選要判第 8 關，呼叫 `evaluate_gate8()` 就有答案，不必再各自寫一套
buy-and-hold 比較。

**「同等風險水準」怎麼判**：裁示原文是「任何主動策略在同等風險水準下贏不過這個被動
基準，一律判失敗」——不是隨便挑 w=0.20 這種固定點比，而是先看候選自己的 MDD，
在被動基準的 12 個 w 點裡找 MDD 最接近的那一個，用它的報酬當比較基準。這是最近鄰
匹配，不是精確風險相等（w 網格是離散的 12 個點，步進 0.02），已知限制寫在
`match_by_risk()` docstring 裡，不假裝比對到小數點後很多位。

**尚未做到的部分（誠實揭露，不留給下一個人誤以為已完成）**：
`MARATHON_PROTOCOL.md` 同一段話還說「屆時要回頭把所有『已通過第2關』的候選重新過
一次第8關」——這裡**只完成了 gate 本身這個可呼叫的函式，沒有回頭批次重評
TRIALS_LEDGER.md／STRATEGY_GRAVEYARD.md／LEADS.md／TW_LEADS.md 裡任何一個既有候選**。
那是後續一輪獨立的工作量（要先盤點有哪些候選宣稱過了第2關，一個一個補跑候選自己的
equity curve 算出 MDD 再呼叫這裡的 gate），不在本項範圍內，登記在
`PENDING_QUEUE.md` 深讀二.3。

執行方式：
    python passive_benchmark_gate.py --self-test   # 不碰網路，純邏輯測試
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

RESULT_PATH = Path(__file__).resolve().parent.parent / "data" / "passive_benchmark_tw_v1_result.json"


@dataclass
class PassiveBenchmarkRow:
    w: float
    return_pct: float
    mdd_pct: float
    sortino: float
    n_trades: int


def load_passive_benchmark(phase: str, *, path: Path = RESULT_PATH) -> list[PassiveBenchmarkRow]:
    """讀 `passive_benchmark_tw_v1.py --run` 產生的真實結果檔，phase 為 'TRAIN' 或 'VAL'。

    找不到檔案就直接拋錯，不回傳假的/預設的基準列——沒有真實跑過的數字，這關就是
    不能判，寧可讓呼叫端知道「還沒有基準可比」而中止，不能安靜地用0或None矇混過去。
    """
    if not path.exists():
        raise FileNotFoundError(
            f"找不到被動基準結果 {path}——先跑 `python passive_benchmark_tw_v1.py --run` 產生，"
            "這個gate拒絕在沒有真實基準數字的情況下判定。"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    phases = data.get("phases", {})
    if phase not in phases or not phases[phase]:
        raise KeyError(f"被動基準結果沒有非空的 {phase!r} phase，現有：{list(phases.keys())}")
    rows = [PassiveBenchmarkRow(w=float(w), **v) for w, v in phases[phase].items()]
    rows.sort(key=lambda r: r.w)
    return rows


def match_by_risk(rows: list[PassiveBenchmarkRow], candidate_mdd_pct: float) -> PassiveBenchmarkRow:
    """在被動基準的 w 網格裡，找 MDD（負值，越負代表回撤越深）最接近候選的那一點。

    這是最近鄰匹配，不是連續函數插值——w 網格只有 12 個離散點（步進0.02），
    TRAIN期MDD範圍約-6.6%~-24.4%、VAL期約-3.1%~-11.4%，網格間距對應的MDD落差
    大約1.5~2個百分點，候選的MDD若落在兩個網格點中間，會被歸到較接近的那一個，
    不做線性內插（內插等於在12個真實模擬點之外憑空造出被動基準沒有真的跑過的
    風險水準，違反「不得出現假資料」的原則）。
    """
    if not rows:
        raise ValueError("rows 不能是空的")
    return min(rows, key=lambda r: abs(r.mdd_pct - candidate_mdd_pct))


def evaluate_gate8(
    *, phase: str, candidate_name: str, candidate_return_pct: float, candidate_mdd_pct: float,
    path: Path = RESULT_PATH,
) -> dict:
    """Gate 8：候選在「跟被動基準風險最接近的w點」上，報酬是否贏過被動基準。

    回傳完整比較明細（不折疊成單一bool），方便寫進TRIALS_LEDGER時能交代清楚是在
    哪個風險水準、哪個phase下比較的，符合「復盤看流程不只看盈虧」的紀律——一個
    candidate若只在VAL期贏、TRAIN期輸，那本身就是要追查的訊號，不是把兩期平均
    模糊掉。
    """
    rows = load_passive_benchmark(phase, path=path)
    matched = match_by_risk(rows, candidate_mdd_pct)
    passed = candidate_return_pct > matched.return_pct
    return {
        "gate": 8,
        "candidate_name": candidate_name,
        "phase": phase,
        "passed": passed,
        "candidate_return_pct": candidate_return_pct,
        "candidate_mdd_pct": candidate_mdd_pct,
        "matched_benchmark_w": matched.w,
        "matched_benchmark_return_pct": matched.return_pct,
        "matched_benchmark_mdd_pct": matched.mdd_pct,
        "matched_benchmark_sortino": matched.sortino,
        "note": "最近鄰w匹配，非連續風險相等；見match_by_risk() docstring",
    }


# ---------------------------------------------------------------- self-test

def self_test() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    rows = [
        PassiveBenchmarkRow(w=0.08, return_pct=8.0, mdd_pct=-6.0, sortino=0.2, n_trades=100),
        PassiveBenchmarkRow(w=0.20, return_pct=20.0, mdd_pct=-16.0, sortino=0.23, n_trades=130),
        PassiveBenchmarkRow(w=0.30, return_pct=30.0, mdd_pct=-24.0, sortino=0.23, n_trades=137),
    ]

    # 1. 最近鄰匹配：MDD -15.5 應該匹配到 w=0.20（-16.0）而不是 w=0.08 或 w=0.30。
    m = match_by_risk(rows, candidate_mdd_pct=-15.5)
    check("MDD最接近的w點匹配正確", m.w == 0.20, f"matched w={m.w}")

    # 2. 候選報酬贏過匹配到的基準點 → passed=True（直接驗證passed判定邏輯本身，
    #    不透過evaluate_gate8()——那個函式綁定真實結果檔路徑，邏輯驗證用rows fixture更乾淨）。
    matched = match_by_risk(rows, -15.5)
    passed = 25.0 > matched.return_pct
    check("候選報酬贏過同風險水準基準應判passed=True", passed is True, f"25.0 vs {matched.return_pct}")

    # 3. 候選報酬輸給匹配基準點 → passed=False。
    matched2 = match_by_risk(rows, -15.5)
    passed2 = 15.0 > matched2.return_pct
    check("候選報酬輸給同風險水準基準應判passed=False", passed2 is False, f"15.0 vs {matched2.return_pct}")

    # 4. 空rows要拋錯，不能安靜回傳假匹配。
    try:
        match_by_risk([], -10.0)
        check("空benchmark列表必須拋錯", False, "沒有拋錯")
    except ValueError:
        check("空benchmark列表必須拋錯", True)

    # 5. 找不到結果檔要拋錯，不能回傳假的基準列。
    try:
        load_passive_benchmark("TRAIN", path=Path("/tmp/__does_not_exist__.json"))
        check("結果檔不存在必須拋錯", False, "沒有拋錯")
    except FileNotFoundError:
        check("結果檔不存在必須拋錯", True)

    # 6. 對真實結果檔跑一次完整evaluate_gate8()，確認能讀到目前真正存在的12個w點資料
    #    （不是自我循環驗證——用一個已知會贏/已知會輸的極端數字各測一次）。
    if RESULT_PATH.exists():
        win = evaluate_gate8(phase="VAL", candidate_name="self_test_extreme_win",
                              candidate_return_pct=9999.0, candidate_mdd_pct=-7.7)
        check("對真實結果檔：極端高報酬必定passed=True", win["passed"] is True, json.dumps(win, ensure_ascii=False))
        lose = evaluate_gate8(phase="VAL", candidate_name="self_test_extreme_lose",
                               candidate_return_pct=-9999.0, candidate_mdd_pct=-7.7)
        check("對真實結果檔：極端低報酬必定passed=False", lose["passed"] is False, json.dumps(lose, ensure_ascii=False))
    else:
        print("  [SKIP] 真實結果檔不存在，跳過第6項（純邏輯測試不受影響）")

    print(f"\n=== self-test {'全部通過' if not failures else f'{len(failures)} 項 FAIL'} ===")
    return 0 if not failures else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
