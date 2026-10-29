"""自測：集保千張大戶抓取 `scripts/fetch_tdcc_holders.py` 的略過邏輯與週數連續性（先.一三五-1bf）。

模擬 K（paper_11）資料來源；排程每日 09:00 跑，同週略過全靠這幾個函式。暫存目錄、零外部請求（不呼叫 fetch_raw）。
1. _save_snapshot：新週存檔、同週已存不覆寫、多日期回應取列數最多者、空 CSV 不寫。
2. _snapshot_exists：已存 → True；未存／壞 CSV → False（不拋錯）。
3. _already_built：holders.json 含該週才 True；壞檔／不存在／None → False。
4. _streak：連漲／連跌／持平／空、缺週（相隔 >9 天）中斷。
5. main：同週已存且 holders.json 已含 → 不呼叫 build_holders_json。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_tdcc_holders as T  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def csv_text(rows: list[tuple[str, str]]) -> str:
    """合成 CSV（數字皆假）：rows＝[(資料日期, 代號)]，每檔只放合計一格。"""
    body = "\n".join(f"{d},{c},17,1,1,100.00" for d, c in rows)
    return T.EXPECTED_HEADER + "\n" + body + "\n"


orig = (T.TDCC_DIR, T.OUT, T.fetch_raw, T.build_holders_json)
with tempfile.TemporaryDirectory() as td:
    try:
        T.TDCC_DIR = Path(td) / "tdcc"
        T.OUT = Path(td) / "holders.json"

        print("1／2. _save_snapshot／_snapshot_exists")
        w1 = csv_text([("20261024", "2330"), ("20261024", "2317")])
        check("未存 → _snapshot_exists False", T._snapshot_exists(w1) is False)
        check("新週存檔回傳日期", T._save_snapshot(w1) == "20261024" and (T.TDCC_DIR / "20261024.csv").exists())
        check("已存 → _snapshot_exists True", T._snapshot_exists(w1) is True)
        w1b = csv_text([("20261024", "9999")])
        check("同週再存回傳日期", T._save_snapshot(w1b) == "20261024")
        check("同週不覆寫", (T.TDCC_DIR / "20261024.csv").read_text(encoding="utf-8") == w1)
        mixed = csv_text([("20261031", "2330"), ("20261031", "2317"), ("20261024", "1101")])
        check("多日期取列數最多者", T._save_snapshot(mixed) == "20261031")
        check("空 CSV 不寫、回 None", T._save_snapshot(T.EXPECTED_HEADER + "\n") is None)
        check("壞 CSV（短列）→ _snapshot_exists False", T._snapshot_exists("表頭\na,b\n") is False)
        check("空字串 → _snapshot_exists False（不拋錯）", T._snapshot_exists("") is False)

        print("3. _already_built")
        check("holders.json 不存在 → False", T._already_built("20261024") is False)
        T.OUT.write_text(json.dumps({"meta": {"dates_available": ["20261017", "20261024"]}}), encoding="utf-8")
        check("含該週 → True", T._already_built("20261024") is True)
        check("不含該週 → False", T._already_built("20261031") is False)
        check("None → False", T._already_built(None) is False)
        T.OUT.write_text("{壞", encoding="utf-8")
        check("壞檔 → False", T._already_built("20261024") is False)

        print("4. _streak")
        check("空 → 0", T._streak([]) == 0)
        check("連漲 3", T._streak([-1, 1, 2, 3]) == 3)
        check("連跌 2", T._streak([1, -1, -2]) == -2)
        check("最新持平 → 0", T._streak([1, 2, 0]) == 0)
        check("缺週中斷（最後一期相隔 14 天之前不算）", T._streak([1, 2, 3], gaps=[7, 14, 7]) == 1)
        check("最新一期本身跨缺週 → 0", T._streak([1, 2], gaps=[7, 14]) == 0)
        check("9 天不算缺週", T._streak([1, 2], gaps=[7, 9]) == 2)

        print("5. main 略過")
        built: list[int] = []
        T.build_holders_json = lambda: built.append(1) or 0
        T.fetch_raw = lambda: w1
        T.OUT.write_text(json.dumps({"meta": {"dates_available": ["20261024"]}}), encoding="utf-8")
        check("同週已存且已含 → 不重產", T.main() == 0 and built == [])
        T.OUT.write_text(json.dumps({"meta": {"dates_available": ["20261017"]}}), encoding="utf-8")
        check("同週已存但 holders.json 未含 → 重產", T.main() == 0 and built == [1])
        T.fetch_raw = lambda: None
        check("抓取失敗 → 用既有快照重產", T.main() == 0 and built == [1, 1])
    finally:
        T.TDCC_DIR, T.OUT, T.fetch_raw, T.build_holders_json = orig

print(f"\n{ok} 通過，{fail} 失敗")
sys.exit(1 if fail else 0)
