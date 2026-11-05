# -*- coding: utf-8 -*-
"""先.一三五-1lm（2026-11-06）自測：本機新聞補班 `news_local_fallback.OUTPUTS` 必須與
.github/workflows/news_events.yml commit 步驟所有 `git add` 行的路徑完全一致。

為什麼：先.一三五-1le 是「本機補跑只照 yml 一部分提交」——market 那支從 yml 擷取時只抓第一行，
10/29～11/05 只提交停資停券資料夾。news 這支不讀 yml、寫死清單，現在一致，但 yml 日後加輸出檔時
沒有人提醒要同步這份清單；本自測補上這道守門（十節：排程會改寫的檔要進對應清單）。
零外部請求、不讀 git。不一致 exit 1。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import news_local_fallback as N  # noqa: E402

YML = ROOT / ".github" / "workflows" / "news_events.yml"
results = []


def check(label: str, ok: bool) -> None:
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + label)


def yml_add_paths(text: str) -> set[str]:
    """收所有非註解的 `git add` 行，取出路徑（去掉選項、`--`、重導向與 `|| true`、尾斜線）。"""
    out = set()
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("#") or not s.startswith("git add"):
            continue
        s = re.split(r"\s(?:2>|\|\||&&|;)", s)[0]
        for tok in s.split()[2:]:
            if tok.startswith("-"):
                continue
            out.add(tok.rstrip("/"))
    return out


def main() -> int:
    yml_paths = yml_add_paths(YML.read_text(encoding="utf-8"))
    outs = {p.rstrip("/") for p in N.OUTPUTS}
    check(f"yml 解析到路徑（{len(yml_paths)} 個）", len(yml_paths) >= 5)
    miss = sorted(yml_paths - outs)
    extra = sorted(outs - yml_paths)
    check("yml 有、本機補班 OUTPUTS 沒有：" + ("無" if not miss else "、".join(miss)), not miss)
    check("本機補班 OUTPUTS 有、yml 沒有：" + ("無" if not extra else "、".join(extra)), not extra)
    # 解析器自身：註解行、`|| true`、選項不能被當成路徑
    syn = "# git add data/註解.json\n  git add -- data/a.json 2>/dev/null || true\n  git add -A data/b/ data/c.json\n"
    check("合成：只收 a、b、c，註解與選項不算", yml_add_paths(syn) == {"data/a.json", "data/b", "data/c.json"})
    print(f"{sum(results)}/{len(results)} PASS")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
