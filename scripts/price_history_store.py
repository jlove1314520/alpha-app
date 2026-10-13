# -*- coding: utf-8 -*-
"""price_history 拆檔存取（2026-10-13 總司令【先.八十二】1）。

背景：data/price_history.json 單檔約 72～75MB，逼近 GitHub 單檔 100MB 硬上限。
改成資料夾 data/price_history/：
  _meta.json        原本的 meta＋代號原始順序（code_order），讓讀回來的 dict 順序與拆檔前完全相同
  b0.json … b9.json 依代號最後一碼分桶（最後一碼不是數字的放 bx.json），每檔 {"prices": {代號: [列…]}}
每列一行（不縮排欄位），檔案小、git 差異也只到「列」。每檔遠小於 20MB。

所有讀寫端一律呼叫這裡：
  load(path)   path 是舊的邏輯路徑（…/data/price_history.json）。該檔存在就照舊讀單檔
               （自測用的暫存單檔、過渡期相容）；不存在就讀同層的 price_history/ 資料夾。
  exists(path) 單檔或資料夾任一存在即 True。
  save(doc, path)  path 是正式路徑（repo 的 data/price_history.json）→ 寫拆檔、刪掉舊單檔；
               其他路徑（自測暫存檔）→ 照舊寫單檔。每個檔先寫暫存檔再 os.replace（原子替換）。
讀取有重試（先.八十一-31：本機 git pull 換檔時檔案可能短暫不存在）。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "data" / "price_history.json"
BUCKETS = [str(i) for i in range(10)] + ["x"]


def bucket_of(code: str) -> str:
    c = str(code)[-1:] if code else ""
    return c if c.isdigit() else "x"


def split_dir(path: Path | str = CANONICAL) -> Path:
    p = Path(path)
    return p.with_suffix("")  # …/price_history.json → …/price_history


def _read(p: Path, retries: int = 5):
    last = None
    for i in range(retries):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as e:
            last = e
            time.sleep(0.4 * (i + 1))
    raise last


def exists(path: Path | str = CANONICAL) -> bool:
    p = Path(path)
    return p.exists() or (split_dir(p) / "_meta.json").exists()


def load(path: Path | str = CANONICAL, codes=None) -> dict:
    """回傳與拆檔前 json.load(price_history.json) 完全相同的 {"meta":…, "prices":{…}}。
    codes 給了就只讀需要的分桶、只回那些代號（順序仍照原始順序）。"""
    p = Path(path)
    if p.exists():
        doc = _read(p)
        if codes is not None:
            want = set(map(str, codes))
            doc = dict(doc)
            doc["prices"] = {k: v for k, v in (doc.get("prices") or {}).items() if k in want}
        return doc
    d = split_dir(p)
    head = _read(d / "_meta.json")
    order = head.get("code_order") or []
    need = BUCKETS if codes is None else sorted({bucket_of(c) for c in codes})
    merged: dict = {}
    for b in need:
        f = d / f"b{b}.json"
        if f.exists():
            merged.update(_read(f).get("prices") or {})
    want = None if codes is None else set(map(str, codes))
    prices = {}
    for c in order:
        if c in merged and (want is None or c in want):
            prices[c] = merged[c]
    for c, v in merged.items():  # 防呆：分桶裡有、順序表沒有的代號接在最後
        if c not in prices and (want is None or c in want):
            prices[c] = v
    out = {}
    for k, v in head.items():
        if k == "code_order":
            continue
        out[k] = v
    out["prices"] = prices
    # 保持原本頂層鍵順序（meta 在前、prices 在後；其他頂層鍵照 _meta 記的順序）
    keys = head.get("top_keys") or [k for k in out if k != "prices"] + ["prices"]
    return {k: out[k] for k in keys if k in out}


def _atomic_write(p: Path, text: str) -> None:
    tmp = p.with_name(p.name + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    for i in range(10):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            time.sleep(0.5 * (i + 1))
    os.replace(tmp, p)


def _dump_bucket(prices: dict) -> str:
    """每列一行：{"prices": {"2330": [\n  {...},\n  {...}\n ], ...}}"""
    parts = []
    for code, rows in prices.items():
        body = ",\n".join("  " + json.dumps(r, ensure_ascii=False, allow_nan=False) for r in rows)
        parts.append(json.dumps(code, ensure_ascii=False) + ": [\n" + body + "\n ]")
    return '{"prices": {\n' + ",\n".join(parts) + "\n}}\n"


def save(doc: dict, path: Path | str = CANONICAL, split: bool | None = None) -> dict:
    """寫回。正式路徑寫拆檔並刪舊單檔；回傳 {bucket: bytes} 方便記錄大小。"""
    p = Path(path)
    if split is None:
        split = p.resolve() == CANONICAL.resolve()
    if not split:
        _atomic_write(p, json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False))
        return {p.name: p.stat().st_size}
    d = split_dir(p)
    d.mkdir(parents=True, exist_ok=True)
    prices = doc.get("prices") or {}
    groups: dict = {b: {} for b in BUCKETS}
    for code, rows in prices.items():
        groups[bucket_of(code)][code] = rows
    sizes = {}
    for b in BUCKETS:
        f = d / f"b{b}.json"
        _atomic_write(f, _dump_bucket(groups[b]))
        sizes[f.name] = f.stat().st_size
    head = {k: v for k, v in doc.items() if k != "prices"}
    head["top_keys"] = list(doc.keys())
    head["code_order"] = list(prices.keys())
    _atomic_write(d / "_meta.json", json.dumps(head, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    sizes["_meta.json"] = (d / "_meta.json").stat().st_size
    if p.exists():
        p.unlink()
    return sizes


def latest_mtime(path: Path | str = CANONICAL) -> float | None:
    """單檔或拆檔資料夾最後修改時間（給新鮮度檢查用）。"""
    p = Path(path)
    if p.exists():
        return p.stat().st_mtime
    d = split_dir(p)
    ts = [f.stat().st_mtime for f in d.glob("*.json")] if d.exists() else []
    return max(ts) if ts else None


if __name__ == "__main__":  # 一次性轉檔：python scripts/price_history_store.py migrate
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        src = _read(CANONICAL)
        sizes = save(src, CANONICAL)
        print(json.dumps(sizes, ensure_ascii=False))
