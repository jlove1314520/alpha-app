# -*- coding: utf-8 -*-
"""先.八十一-63（2026-10-13）：四步驗證的 log 解析自測——只取最後一次啟動的 [build] 行、token 行絕不進結果。
用法：python scripts/selftest_live_server_verify.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import live_server_verify as V  # noqa: E402

FAKE_TOKEN = "FAKETOKEN0123456789abcdefABCDEF"
log = Path(tempfile.mkdtemp()) / "out.log"
log.write_text("\n".join([
    "[build] git sha=1111111　原始碼修改時間=2026-10-12T10:00:00+08:00",
    "[build] source_hash=aaaaaaaaaaaa deps=auto_ledger_view:bbbbbbbbbbbb",
    f"本機驗證token（貼進App設定頁「即時伺服器」卡片）：{FAKE_TOKEN}",
    "[build] git sha=2222222　原始碼修改時間=2026-10-13T10:00:00+08:00",
    f"本機驗證token（貼進App設定頁「即時伺服器」卡片）：{FAKE_TOKEN}",
]) + "\n", encoding="utf-8")
b = V.build_lines(log)
res = [("①取最後一次啟動的 sha", b["sha"] == "2222222"),
       ("②最後一次啟動沒有 source_hash 行→回空（不沿用前一次）", b["source_hash"] is None and b["deps"] == {}),
       ("③結果裡沒有 token", FAKE_TOKEN not in repr(b))]
log.write_text(log.read_text(encoding="utf-8") + "[build] source_hash=cccccccccccc deps=auto_ledger_view:dddddddddddd,web_push:eeeeeeeeeeee\n", encoding="utf-8")
b = V.build_lines(log)
res.append(("④讀到新的 source_hash 與 deps", b["source_hash"] == "cccccccccccc" and b["deps"] == {"auto_ledger_view": "dddddddddddd", "web_push": "eeeeeeeeeeee"}))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
