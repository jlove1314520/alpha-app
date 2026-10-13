# -*- coding: utf-8 -*-
"""先.八十二-13（2026-10-13）：處置／注意股提醒自測（暫存檔＋假推播，不碰真設定、不送真推播）。
① 自選股被列入處置 → 推播一次、內容含代號／名稱／期間  ② 真錢持股被列入注意 → 推播並標「真錢持股」
③ 同一筆第二次不再推  ④ 不在自選也非持股 → 不推  ⑤ 推播沒送達 → 不記已推，下一輪重試
用法：python scripts/selftest_disposal_alert.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import disposal_alert as A  # noqa: E402

tmp = Path(tempfile.mkdtemp())
A.FLAGS, A.SETTINGS, A.LIVE_WL, A.STATE = tmp / "f.json", tmp / "s.json", tmp / "w.json", tmp / "st.json"
A.SETTINGS.write_text(json.dumps({"settings": {"watchlist": ["2330"], "watchlists": {"lists": {"B": ["6669"]}}}}), encoding="utf-8")
A.LIVE_WL.write_text(json.dumps({"codes": ["2454"]}), encoding="utf-8")
A.holding_codes = lambda: {"0050", "00646", "00697B"}
A.names = lambda: {"2330": "台積電", "0050": "元大台灣50"}
sent = []
ok_send = lambda t, b: (sent.append((t, b)), {"ok": 1})[1]  # noqa: E731
A.FLAGS.write_text(json.dumps({"disposal": {"2330": {"start": "2026-10-14", "end": "2026-10-27", "interval": "20分鐘"},
                                            "9999": {"start": "2026-10-14", "end": "2026-10-27"}},
                               "notice": {"0050": {"announced": "2026-10-14"}}}), encoding="utf-8")
r = A.main(send=ok_send)
res = [("①自選股處置→推播、含代號名稱期間", r["new"] == 2 and len(sent) == 1 and "2330 台積電" in sent[0][1] and "10-14～10-27" in sent[0][1] and "20分鐘" in sent[0][1]),
       ("②真錢持股注意→標真錢持股", "0050 元大台灣50（真錢持股）列入注意股" in sent[0][1]),
       ("④不在自選也非持股（9999）→不推", "9999" not in sent[0][1])]
r = A.main(send=ok_send)
res.append(("③同一筆第二次不再推", r["new"] == 0 and len(sent) == 1))
A.FLAGS.write_text(json.dumps({"disposal": {"6669": {"start": "2026-10-20", "end": "2026-11-02"}}, "notice": {}}), encoding="utf-8")
r = A.main(send=lambda t, b: {"ok": 0, "errors": ["NO_SUBSCRIPTION"]})
r2 = A.main(send=ok_send)
res.append(("⑤沒送達不記已推、下一輪重試（多清單自選 6669）", r["pushed"] == 0 and r2["new"] == 1 and len(sent) == 2))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
