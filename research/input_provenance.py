# -*- coding: utf-8 -*-
"""input_provenance.py — 單發 runner 的「不進 repo 中間檔」可重現紀錄（先.十六-二，
2026-10-05 總司令裁示）。

research/data/ 整個被 .gitignore，所以 *.pkl 面板／流動性檔不在版本控制裡；
單發回測的結果 json 若不記下當時讀的是哪個版本的檔，事後無法證明「結果對應哪份輸入」
（#409 撞車時就是這個缺口）。用法：runner 寫 result.json 前呼叫

    res["inputs"] = describe_inputs([
        {"path": PANEL, "build_script": "research/supply_tightness_panel.py", "params": {...}},
        ...])

每個檔記錄 sha256／大小／檔案修改時間（當作建置時間）／建置腳本／參數。
守門員原則（CLAUDE.md 十二）：單檔記錄失敗只在該檔寫 error 欄位，不中斷 runner。
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def describe_inputs(specs: list[dict], retroactive: str | None = None) -> list[dict]:
    """specs: [{path, build_script, params}]；retroactive 非 None 時每筆標註為事後補記（附說明）。"""
    out = []
    for sp in specs:
        p = Path(sp["path"])
        rec = {"path": str(p).replace("\\", "/"),
               "build_script": sp.get("build_script"),
               "params": sp.get("params"),
               "retroactive": bool(retroactive)}
        if retroactive:
            rec["retroactive_note"] = retroactive
        try:
            st = p.stat()
            rec["size_bytes"] = st.st_size
            rec["built_at_mtime"] = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
            rec["sha256"] = sha256_file(p)
        except Exception as e:  # noqa: BLE001 -- 單檔失敗只降級
            rec["error"] = f"{type(e).__name__}: {e}"
        out.append(rec)
    return out
