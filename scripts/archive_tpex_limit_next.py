"""先.一三八-4：上櫃次日漲跌停價本機累積（零外部請求）。

雲端 market.yml 每班覆寫 data/tpex_limit_next.json（.github/scripts/update_price_history.py），
每個版本都留在 git 歷史裡。本程式把「git 歷史各版本＋工作目錄目前這份」依 data_date 展開成
research/data/tpex_limit_next/<data_date>.json（gitignore，不進公開 repo）：
  - 同一 data_date 有多個版本時取最新 commit 那一版（git log 由新到舊，先看到的為準）；
  - 已存在的日期不覆寫；讀不到／壞掉的版本（含 data_date 不是 YYYY-MM-DD）只略過並計數（十二節）。

用法：python scripts/archive_tpex_limit_next.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 主控台不支援時照舊輸出
    pass

ROOT = Path(__file__).resolve().parent.parent
REL = "data/tpex_limit_next.json"
OUT_DIR = ROOT / "research" / "data" / "tpex_limit_next"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")


def versions() -> list[tuple[str, str]]:
    """回傳 [(來源標記, 檔案內容)]，工作目錄那份排第一，其後依 commit 由新到舊。"""
    out = []
    cur = ROOT / REL
    if cur.exists():
        out.append(("worktree", cur.read_text(encoding="utf-8")))
    try:
        shas = _git("log", "--format=%H", "--", REL).split()
    except Exception as e:  # noqa: BLE001 —— 不在 git 環境只用工作目錄那份
        print(f"[warn] 讀 git 歷史失敗（只用工作目錄版本）：{e!r}")
        shas = []
    for sha in shas:
        try:
            out.append((sha[:10], _git("show", f"{sha}:{REL}")))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {sha[:10]} 讀不到：{e!r}")
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen, written, bad = set(), 0, 0
    for tag, text in versions():
        try:
            doc = json.loads(text)
            date = doc["data_date"]
            if not isinstance(doc.get("rows"), dict) or not date:
                raise ValueError("缺 rows／data_date")
            # 先.一三五-1bn：資料日當檔名用，格式不對（含 / 或 ..）會拋 FileNotFoundError 中斷整批、或寫到歸檔目錄外
            if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                raise ValueError(f"data_date 不是 YYYY-MM-DD：{date!r}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"[warn] {tag} 版本格式不對，略過：{e!r}")
            continue
        if date in seen:
            continue
        seen.add(date)
        f = OUT_DIR / f"{date}.json"
        if f.exists():
            continue
        doc["archived_from"] = tag
        f.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written += 1
    print(f"[archive_tpex_limit_next] 版本裡的資料日 {len(seen)} 個、新寫 {written} 檔、壞版本 {bad} 個 → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
