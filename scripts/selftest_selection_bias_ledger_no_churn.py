"""自測：`research/selection_bias_ledger.py` 只在總 N 變動時才回寫 TRIALS_LEDGER.md 開頭那行（先.一三五-1jp）。

真實帳本複製到暫存目錄，LEDGER／OUT_MD／OUT_JSON 全換暫存路徑：零外部請求、不動真實帳本與輸出檔。
守住：①N 沒變（只是換一天重跑）→ 帳本位元組不變（原本每天把日期改成今天，追蹤檔長期留在工作目錄沒提交）；
②N 變了 → 數字與日期都更新；③--check 不寫任何檔；④⑤（先.一三五-1jq）SELECTION_BIAS_LEDGER.md 只有時間那行不同不重寫、內容變了照常重寫。
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import selection_bias_ledger as S  # noqa: E402

ok = fail = 0
PAT = re.compile(r"\*\*目前累積總數（可統計檢定的試驗）：(\d+)\*\*（(\d{4}-\d{2}-\d{2})")


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def run(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["selection_bias_ledger.py", *argv]
    try:
        return S.main()
    finally:
        sys.argv = old


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    led = td / "TRIALS_LEDGER.md"
    shutil.copyfile(ROOT / "research" / "TRIALS_LEDGER.md", led)
    S.ROOT = td  # main() 結尾用 OUT_MD.relative_to(ROOT) 印路徑
    S.LEDGER, S.OUT_MD, S.OUT_JSON = led, td / "SBL.md", td / "data" / "sbl.json"

    run([])  # 先跑一次取得目前 N（N 若與真實帳本開頭不同會照常回寫）
    m = PAT.search(led.read_text(encoding="utf-8"))
    check("開頭那行找得到數字與日期", bool(m))
    n_now = int(m.group(1)) if m else -1

    # ① N 相同、日期改成很舊 → 不得回寫
    txt = led.read_text(encoding="utf-8")
    old_date = PAT.sub(lambda mm: mm.group(0).replace(mm.group(2), "2000-01-01"), txt, count=1)
    led.write_text(old_date, encoding="utf-8", newline="\n")
    before = led.read_bytes()
    run([])
    check("N 沒變 → 帳本位元組不變（日期不被改成今天）", led.read_bytes() == before)

    # ② N 不同 → 數字與日期都更新
    wrong = PAT.sub(lambda mm: mm.group(0).replace(mm.group(1), "1", 1), old_date, count=1)
    led.write_text(wrong, encoding="utf-8", newline="\n")
    run([])
    m2 = PAT.search(led.read_text(encoding="utf-8"))
    check("N 變了 → 數字回寫成實算值", bool(m2) and int(m2.group(1)) == n_now, m2 and m2.group(1))
    check("N 變了 → 日期改成今天（不是 2000-01-01）", bool(m2) and m2.group(2) != "2000-01-01", m2 and m2.group(2))

    # ④（先.一三五-1jq）SELECTION_BIAS_LEDGER.md 只有「自動產生（時間）」那行不同 → 不得回寫
    stamp = re.compile(r"(\*\*自動產生\*\*：`research/selection_bias_ledger\.py`（)[^）]*(）。)")
    md_txt = S.OUT_MD.read_text(encoding="utf-8")
    check("SBL.md 找得到「自動產生（時間）」那行", bool(stamp.search(md_txt)))
    S.OUT_MD.write_text(stamp.sub(r"\g<1>2000-01-01 00:00\g<2>", md_txt, count=1), encoding="utf-8", newline="\n")
    before_md = S.OUT_MD.read_bytes()
    run([])
    check("SBL.md 內容沒變 → 位元組不變（時間不被改成現在）", S.OUT_MD.read_bytes() == before_md)
    # ⑤ 內容真的不同 → 照常重寫
    S.OUT_MD.write_text(md_txt + "\n殘留舊內容\n", encoding="utf-8", newline="\n")
    run([])
    check("SBL.md 內容變了 → 重寫（舊內容消失、時間不是 2000-01-01）",
          "殘留舊內容" not in S.OUT_MD.read_text(encoding="utf-8") and "2000-01-01 00:00" not in S.OUT_MD.read_text(encoding="utf-8"))

    # ③ --check 不寫檔
    led.write_text(wrong, encoding="utf-8", newline="\n")
    for p in (S.OUT_MD, S.OUT_JSON):
        p.unlink(missing_ok=True)
    run(["--check"])
    check("--check 不改帳本", led.read_text(encoding="utf-8") == wrong)
    check("--check 不寫輸出檔", not S.OUT_MD.exists() and not S.OUT_JSON.exists())

print(f"\n通過 {ok}／{ok + fail}")
sys.exit(1 if fail else 0)
