# -*- coding: utf-8 -*-
"""自測：.github/scripts/refresh_status_after_rebase.py（先.一三五-1lu）。全部用暫存檔＋假 g，不碰 repo 的 STATUS.json。"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rsar", ROOT / ".github" / "scripts" / "refresh_status_after_rebase.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS {name}")
    else:
        fail += 1
        print(f"FAIL {name}")


class G:
    def __init__(self, df_exc=False, sh_exc=False, lite_exc=False):
        self.df_exc, self.sh_exc, self.lite_exc = df_exc, sh_exc, lite_exc
        self.lite_called = False

    def build_data_files(self):
        if self.df_exc:
            raise RuntimeError("df boom")
        return [{"path": "data/a.json", "status": "ok"}]

    def build_schedule_health(self):
        if self.sh_exc:
            raise RuntimeError("sh boom")
        return {"any_overdue": False}

    def write_status_lite(self, p):
        self.lite_called = True
        if self.lite_exc:
            raise RuntimeError("lite boom")


NOW = datetime(2026, 11, 6, 1, 54, tzinfo=timezone.utc)
MAIN = {"updated_at": "x", "local_schedule_heartbeat": {"k": 1}, "any_overdue": True,
        "data_files": [{"path": "data/a.json", "status": "stale"}]}

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "STATUS.json"
    # 1 正常：stale 被重算掉、其他欄位（心跳）原樣保留、LF、lite 有呼叫
    p.write_text(json.dumps(MAIN), encoding="utf-8")
    g = G()
    r = m.refresh(p, g, NOW, lite=g.write_status_lite)
    d = json.loads(p.read_text(encoding="utf-8"))
    check("1 正常回 True", r is True)
    check("1 data_files 重算", d["data_files"][0]["status"] == "ok")
    check("1 any_overdue 跟 schedule_health", d["any_overdue"] is False)
    check("1 心跳欄位保留", d["local_schedule_heartbeat"] == {"k": 1} and d["updated_at"] == "x")
    check("1 checked_at 台北時間", d["data_files_checked_at"].startswith("2026-11-06T09:54"))
    check("1 LF 換行", b"\r\n" not in p.read_bytes())
    check("1 lite 有重產", g.lite_called)
    check("1 無殘留 tmp", not (Path(td) / "STATUS.json.tmp").exists())
    # 2 data_files 失敗：保留 main 的 data_files，schedule_health 照算
    p.write_text(json.dumps(MAIN), encoding="utf-8")
    r = m.refresh(p, (_g := G(df_exc=True)), NOW, lite=_g.write_status_lite)
    d = json.loads(p.read_text(encoding="utf-8"))
    check("2 df 失敗仍寫 schedule_health", r is True and d["any_overdue"] is False)
    check("2 df 失敗保留舊 data_files", d["data_files"][0]["status"] == "stale")
    # 3 兩者都失敗：不寫檔
    p.write_text(json.dumps(MAIN), encoding="utf-8")
    before = p.read_bytes()
    r = m.refresh(p, (_g := G(df_exc=True, sh_exc=True)), NOW, lite=_g.write_status_lite)
    check("3 全失敗回 False、檔案不變", r is False and p.read_bytes() == before)
    # 4 壞 JSON：不寫檔、不丟例外
    p.write_text("{壞", encoding="utf-8")
    r = m.refresh(p, (_g := G()), NOW, lite=_g.write_status_lite)
    check("4 壞 JSON 回 False、原檔不動", r is False and p.read_text(encoding="utf-8") == "{壞")
    # 5 檔案不存在
    r = m.refresh(Path(td) / "nope.json", G(), NOW, lite=lambda p: None)
    check("5 不存在回 False", r is False)
    # 6 lite 失敗不影響 STATUS
    p.write_text(json.dumps(MAIN), encoding="utf-8")
    r = m.refresh(p, (_g := G(lite_exc=True)), NOW, lite=_g.write_status_lite)
    check("6 lite 失敗仍回 True", r is True and json.loads(p.read_text(encoding="utf-8"))["data_files"][0]["status"] == "ok")
    # 7 STATUS 是陣列（非物件）
    p.write_text("[]", encoding="utf-8")
    check("7 非物件回 False", m.refresh(p, (_g := G()), NOW, lite=_g.write_status_lite) is False)

print(f"\n{ok} PASS / {fail} FAIL")
sys.exit(1 if fail else 0)
